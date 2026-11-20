#include "Analysis.h"
#include <algorithm>
#include <glob.h>
#include "TInterpreter.h"
#include "MessageService.hpp"
#include <set>
#include <map>
#include <regex>
#include <filesystem>
#include <numeric>
#include <cmath>
#include "GRLUtils.h"
#include <algorithm>


std::vector<TString> Analysis::ExpandAndSort(TString pattern) {
    glob_t globResult;
    glob(pattern.Data(), GLOB_TILDE, nullptr, &globResult);
    
    std::vector<TString> files;
    for (size_t i = 0; i < globResult.gl_pathc; ++i)
        files.emplace_back(globResult.gl_pathv[i]);
    
    globfree(&globResult);
    std::sort(files.begin(), files.end());
    return files;
}

Analysis::Analysis() {
    // Default constructor
}

Analysis::Analysis(TString mainFileTreeName, const std::vector<TString>& mainFiles) 
: m_mainFileTreeName(mainFileTreeName), m_mainFileNames(mainFiles)
{   
    addMainFiles(mainFileTreeName, mainFiles);
}

Analysis::Analysis(TString mainFileTreeName, TString auxFileTreeName, const std::vector<TString>& mainFiles, const std::vector<TString>& auxFiles) 
: m_mainFileTreeName(mainFileTreeName), m_auxFileTreeName(auxFileTreeName), m_mainFileNames(mainFiles), m_auxFileNames(auxFiles)
{
    addMainFiles(mainFileTreeName, mainFiles);
    addAuxFiles(auxFileTreeName, auxFiles);
}

Analysis::Analysis(TString mainFileTreeName, TString mainFiles) 
: m_mainFileTreeName(mainFileTreeName)
{   
    auto files = ExpandAndSort(mainFiles);
    m_mainFileNames = files;
    addMainFiles(mainFileTreeName, files);
}

Analysis::Analysis(TString mainFileTreeName, TString auxFileTreeName, TString mainFiles, TString auxFiles)
: m_mainFileTreeName(mainFileTreeName), m_auxFileTreeName(auxFileTreeName)
{
    auto mainFilesList = ExpandAndSort(mainFiles);
    auto auxFilesList = ExpandAndSort(auxFiles);
    m_mainFileNames = mainFilesList;
    m_auxFileNames = auxFilesList;
    addMainFiles(mainFileTreeName, mainFilesList);
    addAuxFiles(auxFileTreeName, auxFilesList);
}

void Analysis::addMainFiles(TString mainFileTreeName, std::vector<TString> mainFiles) 
{
    m_mainFileTreeName = mainFileTreeName;
    m_mainFileNames = mainFiles;
    m_mainChain = new TChain(mainFileTreeName);
    INFO("Adding ", mainFiles.size(), " main files to chain:");
    for (const auto& file : mainFiles) {
        INFO("Adding main file: ", file);
        m_mainChain->Add(file);
    }
    m_mainChainSet = true;
}

void Analysis::addMainFiles(TString mainFileTreeName, TString mainFiles) 
{   
    auto files = ExpandAndSort(mainFiles);
    addMainFiles(mainFileTreeName, files);
}

void Analysis::addAuxFiles(TString auxFileTreeName, TString auxFiles) 
{
    auto files = ExpandAndSort(auxFiles);
    addAuxFiles(auxFileTreeName, files);
}

void Analysis::addAuxFiles(TString auxFileTreeName, std::vector<TString> auxFiles) 
{

    if (!m_mainChain) {
        std::cerr << "Error: Main chain must be set up before adding aux files." << std::endl;
        return;
    }

    if (m_auxChainSet) {
        std::cerr << "Multiple aux chains not supported" << std::endl;
        return;
    }

    TChain* auxChain = new TChain(auxFileTreeName);
    INFO("Adding ", auxFiles.size(), " aux files to chain:");
    for (const auto& file : auxFiles) {
        INFO("Adding aux file: ", file);
        auxChain->Add(file);
    }
    m_auxChain = auxChain;
    m_auxChainSet = true;   
}

// This would be the simple way to do it if the friend tree approach worked, but it doesn't seem to be working with the current file structure.
//  Keeping this here for reference but implementing a manual map-lookup approach instead.
// I think the fact that the branch is called "event" in the aux files, which apparerently is a reserved name in ROOT, is causing the friend tree approach to fail.
// void Analysis::BuildDataFrame() {
//     if (!m_mainChainSet) {
//             std::cerr << "Error: Main chain is not set up. Please add main files before running the analysis." << std::endl;
//             return;
//         }

//     if (m_auxChainSet) {
//         m_mainChain->GetListOfFiles()->Sort();
//         m_auxChain->GetListOfFiles()->Sort();

//         m_mainChain->BuildIndex("run", "eventID");
        
//         m_auxChain->SetAlias("evtNum", "event");
//         m_auxChain->BuildIndex("run", "evtNum");
//         // m_auxChain->BuildIndex("run", "event");
//         m_mainChain->AddFriend(m_auxChain, "aux");
//     }

//     // Construct the dataframe now that the chain is fully configured
//     m_df = std::make_unique<ROOT::RDataFrame>(*m_mainChain);
//     m_node = *m_df;
        // m_node = m_node->Filter("aux.myVetoNu0_rawCharge35 < 40", "Reduced charge cut");

// }

void Analysis::setGRL(const std::vector<TString>& grlJsons, const std::vector<TString>& grlCSVs) {
    m_runLumiDict = GRLUtils::getRunNumberLumiDict(grlCSVs);
    m_grlTimes = std::make_shared<const GRLUtils::GRLTimes>(GRLUtils::readGRLTimes(grlJsons));
}

namespace {
    // Define GoodTimes / ExcludedTimes as compiled lookups. Templated on the type of the eventTime
    // branch, because RDataFrame needs the exact column type for a compiled (non-JIT) Define.
    template <typename TTime>
    void defineGRLTimeColumnsImpl(Analysis& analysis, std::shared_ptr<const GRLUtils::GRLTimes> grl) {
        analysis.Define("GoodTimes",
            [grl](Int_t run, TTime eventTime) { return grl->stable.contains(run, static_cast<long long>(eventTime)); },
            {"run", "eventTime"}, DATA);
        // Always defined (false for every event if the GRL has no excluded periods)
        analysis.Define("ExcludedTimes",
            [grl](Int_t run, TTime eventTime) { return grl->excluded.contains(run, static_cast<long long>(eventTime)); },
            {"run", "eventTime"}, DATA);
    }
}

void Analysis::defineGRLTimeColumns() {
    if (isMC) return;  // GRL time cuts are data only
    if (!m_grlTimes) {
        throw std::runtime_error("GRL not set: call Analysis::setGRL() before Run()");
    }
    for (int run : m_runNumbers) {
        if (!m_grlTimes->stable.hasRun(run)) {
            WARNING("Run ", run, " has no stable periods in the GRL: all its events will fail the 'Good times' cut.");
        }
    }
    const std::string timeType = m_node->GetColumnType("eventTime");
    if      (timeType == "Int_t"     || timeType == "int")                defineGRLTimeColumnsImpl<Int_t>(*this, m_grlTimes);
    else if (timeType == "UInt_t"    || timeType == "unsigned int")       defineGRLTimeColumnsImpl<UInt_t>(*this, m_grlTimes);
    else if (timeType == "Long64_t"  || timeType == "long long")          defineGRLTimeColumnsImpl<Long64_t>(*this, m_grlTimes);
    else if (timeType == "ULong64_t" || timeType == "unsigned long long") defineGRLTimeColumnsImpl<ULong64_t>(*this, m_grlTimes);
    else throw std::runtime_error("Unsupported type for the eventTime column: " + timeType);
}



// ── Adding columns ──────────────────────────────────────────────────────────

bool Analysis::Define(const std::string& name, const std::string& expression, DataType dataType, const std::string& origin) {
    if (!appliesTo(dataType)) {
        DEBUG("Skipping definition ", name, " (not for this sample)");
        return false;
    }
    checkNewColumnName(name, origin);
    DEBUG("Defining ", name, " = ", expression, "  [", origin, "]");
    m_node = m_node->Define(name, expression);
    recordDefinition("Define", name, expression, dataType, origin);
    return true;
}

void Analysis::Alias(const std::string& alias, const std::string& column, const std::string& origin) {
    checkNewColumnName(alias, origin);
    if (!isColumnDefined(column)) {
        throw std::runtime_error(origin + ": cannot create alias '" + alias + "' for '" + column + "', no column with that name exists");
    }
    DEBUG("Alias ", alias, " -> ", column, "  [", origin, "]");
    m_node = m_node->Alias(alias, column);
    recordDefinition("Alias", alias, column, ALL, origin);
}

void Analysis::checkNewColumnName(const std::string& name, const std::string& origin) {
    if (isColumnDefined(name)) {
        throw std::runtime_error(origin + ": cannot define '" + name + "', a column with that name already exists "
                                 "(input branch, alias or earlier definition). Please use a different name.");
    }
}

void Analysis::recordDefinition(const std::string& kind, const std::string& name, const std::string& expression,
                                DataType dataType, const std::string& origin) {
    m_definitionLog.push_back({kind, name, expression, dataTypeName(dataType), origin});
}

std::string Analysis::joinColumns(const ROOT::RDF::ColumnNames_t& columns) {
    std::string out;
    for (const auto& c : columns) out += (out.empty() ? "" : ", ") + c;
    return out;
}

std::string Analysis::dataTypeName(DataType dataType) {
    switch (dataType) {
        case ALL:    return "ALL";
        case DATA:   return "DATA";
        case MC:     return "MC";
        case ASIMOV: return "ASIMOV";
    }
    return "?";
}

bool Analysis::isColumnDefined(const std::string& columnName) {
    auto columnNames = m_node->GetColumnNames();
    return std::find(columnNames.begin(), columnNames.end(), columnName) != columnNames.end();
}

// ── Selection helpers ───────────────────────────────────────────────────────

// data_type semantics (see config/cuts.yaml):
//   ALL:    every sample
//   DATA:   data only
//   MC:     MC, but not in Asimov mode (truth selection)
//   ASIMOV: all MC, including Asimov mode
bool Analysis::appliesTo(DataType dataType) const {
    switch (dataType) {
        case ALL:    return true;
        case DATA:   return !isMC;
        case MC:     return isMC && !isAsimov;
        case ASIMOV: return isMC;
    }
    return true;
}

DataType Analysis::parseDataType(const std::string& dataType) {
    if (dataType == "ALL")    return ALL;
    if (dataType == "DATA")   return DATA;
    if (dataType == "MC")     return MC;
    if (dataType == "ASIMOV") return ASIMOV;
    throw std::runtime_error("Unknown data_type '" + dataType + "'");
}

bool Analysis::requirementsMet(const std::vector<std::string>& requirements, std::string& why) const {
    auto sourceName = [this]() -> std::string {
        switch (m_reducedChargeSource) {
            case ReducedChargeSource::Aux:    return "aux files";
            case ReducedChargeSource::Native: return "input NTuple";
            case ReducedChargeSource::None:   return "none (--no-reduced-charge)";
        }
        return "?";
    };
    for (const auto& r : requirements) {
        bool ok = true;
        if      (r == "reduced_charge")        ok = m_reducedChargeSource != ReducedChargeSource::None;
        else if (r == "aux_reduced_charge")    ok = m_reducedChargeSource == ReducedChargeSource::Aux;
        else if (r == "native_reduced_charge") ok = m_reducedChargeSource == ReducedChargeSource::Native;
        else if (r == "no_reduced_charge")     ok = m_reducedChargeSource == ReducedChargeSource::None;
        else throw std::runtime_error("Unknown requirement '" + r + "'");
        if (!ok) {
            why = "requires " + r + ", reduced charge source is " + sourceName();
            return false;
        }
    }
    return true;
}

// Book a 1D or 2D histogram at the current point of the selection
void Analysis::bookHistogram(const ConfigUtils::HistogramConfig& cfg) {
    if (!appliesTo(parseDataType(cfg.dataType))) {
        DEBUG("Skipping histogram ", cfg.name, " (data_type ", cfg.dataType, ")");
        ++m_nHistSkipped;
        return;
    }
    std::string why;
    if (!requirementsMet(cfg.requirements, why)) {
        DEBUG("Skipping histogram ", cfg.name, " (", why, ")");
        ++m_nHistSkipped;
        return;
    }
    for (const auto* axis : {&cfg.x, cfg.y ? &*cfg.y : nullptr}) {
        if (axis && !isColumnDefined(axis->variable)) {
            WARNING("Histogram '", cfg.name, "': column '", axis->variable, "' does not exist in the dataframe. Histogram not booked.");
            ++m_nHistSkipped;
            return;
        }
    }

    const auto& x = cfg.x;
    if (!cfg.y) {
        DEBUG("Booking 1D histogram ", cfg.name, " of ", x.variable);
        const auto model = x.hasEdges()
            ? ROOT::RDF::TH1DModel(cfg.name.c_str(), cfg.title.c_str(), static_cast<int>(x.edges.size()) - 1, x.edges.data())
            : ROOT::RDF::TH1DModel(cfg.name.c_str(), cfg.title.c_str(), x.nBins, x.min, x.max);
        m_histResults.push_back(m_node->Histo1D(model, x.variable));
        return;
    }

    const auto& y = *cfg.y;
    DEBUG("Booking 2D histogram ", cfg.name, " of ", y.variable, " vs ", x.variable);
    const char* n = cfg.name.c_str();
    const char* ti = cfg.title.c_str();
    const int nxe = static_cast<int>(x.edges.size()) - 1, nye = static_cast<int>(y.edges.size()) - 1;
    ROOT::RDF::TH2DModel model;
    if      (!x.hasEdges() && !y.hasEdges()) model = ROOT::RDF::TH2DModel(n, ti, x.nBins, x.min, x.max, y.nBins, y.min, y.max);
    else if ( x.hasEdges() && !y.hasEdges()) model = ROOT::RDF::TH2DModel(n, ti, nxe, x.edges.data(), y.nBins, y.min, y.max);
    else if (!x.hasEdges() &&  y.hasEdges()) model = ROOT::RDF::TH2DModel(n, ti, x.nBins, x.min, x.max, nye, y.edges.data());
    else                                     model = ROOT::RDF::TH2DModel(n, ti, nxe, x.edges.data(), nye, y.edges.data());
    m_histResults.push_back(m_node->Histo2D(model, x.variable, y.variable));
}

// Define the columns of the definitions config, in file order
void Analysis::applyDefinitions() {
    if (!m_definitions) {
        throw std::runtime_error("No definitions config set: call Analysis::setDefinitions() before Run()");
    }
    // Position of each definition in the file, to catch expressions using a definition from further down
    const auto& defs = m_definitions->definitions;
    std::unordered_map<std::string, std::size_t> position;
    for (std::size_t i = 0; i < defs.size(); ++i) position[defs[i].name] = i;
    const std::regex identifier(R"([A-Za-z_][A-Za-z0-9_]*)");

    std::size_t nDefined = 0, nSkipped = 0;
    for (std::size_t i = 0; i < defs.size(); ++i) {
        const auto& d = defs[i];
        std::string why;
        if (!requirementsMet(d.requirements, why)) {
            DEBUG("Skipping definition ", d.name, " (", why, ")");
            ++nSkipped;
            continue;
        }
        for (auto it = std::sregex_iterator(d.expression.begin(), d.expression.end(), identifier); it != std::sregex_iterator(); ++it) {
            const std::string token = it->str();
            auto pos = position.find(token);
            if (pos != position.end() && pos->second > i && !isColumnDefined(token)) {
                throw std::runtime_error(m_definitions->sourcePath + ": definition '" + d.name + "' uses '" + token +
                                         "', which is defined further down the file. Definitions are created in file order: move '" +
                                         token + "' above '" + d.name + "'.");
            }
        }
        if (Define(d.name, d.expression, parseDataType(d.dataType), m_definitions->sourcePath)) ++nDefined;
        else ++nSkipped;
    }
    INFO("Defined ", nDefined, " columns from ", m_definitions->sourcePath, " (", nSkipped,
         " skipped for this sample / reduced charge source; use -v for details).");
}

// Apply the cuts and book the histograms of the selection config, in file order
void Analysis::applySelection() {
    if (!m_selection) {
        throw std::runtime_error("No selection config set: call Analysis::setSelection() before Run()");
    }
    INFO("Applying selection from ", m_selection->sourcePath, "...");

    for (const auto& h : m_selection->histograms) bookHistogram(h);  // before any cut

    for (const auto& cut : m_selection->cuts) {
        std::string why;
        if (!requirementsMet(cut.requirements, why)) {
            INFO("Skipping cut: ", cut.name, " (", why, ")");
        } else {
            applyCut(cut.expression, cut.name, parseDataType(cut.dataType));
        }
        // Histograms attached to a cut are booked at this point of the selection even if the cut
        // itself is not applied to this sample; they have their own data_type / requires.
        for (const auto& h : cut.histograms) bookHistogram(h);
    }

    INFO("Booked ", m_histResults.size(), " histograms (", m_nHistSkipped, " skipped for this sample / reduced charge source; use -v for details).");
}

// Main setup function that builds the dataframe and sets up the aux chain if present
void Analysis::BuildDataFrame() {

    if (!m_mainChainSet) {
        ERROR("Error: Main chain not set up.");
        return;
    }

    // Allow shorter use of vecops functions in strings
    // e.g. DeltaPhi rather than ROOT::VecOps::DeltaPhi 
    gInterpreter->Declare("using namespace ROOT::VecOps;");

    // C++ defines (must not rely on anything defined below)
    gInterpreter->AddIncludePath(PROJECT_INCLUDE_DIR);
    gInterpreter->Declare("#include \"RDFDefines.h\"");

    m_df   = std::make_unique<ROOT::RDataFrame>(*m_mainChain);
    m_node = *m_df;

    const bool hasNativeVeto11 = isColumnDefined("Veto11_raw_charge") || isColumnDefined("VetoSt11_raw_charge");
    const bool hasPreshower23  = isColumnDefined("Preshower2_raw_charge") && isColumnDefined("Preshower3_raw_charge");
    const bool hasMuon         = isColumnDefined("Muon0_raw_charge") && isColumnDefined("Muon1_raw_charge") &&
                                 isColumnDefined("Track_X_atMuon1") && isColumnDefined("Track_X_atMuon2");

    // Backwards compatibility with older NTuples: VetoSt* naming, missing Veto11
    setupVetoCompatibility();
    // 2024 dual calorimeter readout: Calo* -> CaloLo* if there is no single-readout Calo
    setupCaloCompatibility();

    // ── Built-in definitions ────────────────────────────────────────────────
    // These stay in C++ because the built-in reduced-charge code relies on them.
    // All other definitions are in config/definitions.yaml (applied at the end of this function).
    // Run periods (strictly non-overlapping across 2022–2026 DATA and MC families)
    const bool hasNativeReducedCharge = isColumnDefined("VetoNu0_reduced_charge") && isColumnDefined("VetoNu1_reduced_charge");
    Define("isCaloNuPeriod", "15821 <= run  && run <= 16924", DATA);
    Define("isCaloNuPeriod", "(200137 <= run && run <= 200147) || (200172 <= run && run <= 200183)", ASIMOV);  // all MC
    Define("is2022Period", "run < 10000", DATA);
    Define("is2022Period", "(200080 <= run && run <= 200090) || (200104 <= run && run <= 200115)", ASIMOV);
    Define("is2023Period", "10000 <= run && run < 14000", DATA);
    Define("is2023Period", "false", ASIMOV);
    Define("is2024Period", "14000 <= run && run <= 18499", DATA);
    Define("is2024Period", "(200091 <= run && run <= 200101) || (200137 <= run && run <= 200147) || (200160 <= run && run <= 200183)", ASIMOV);  // all MC
    Define("is2025Period", "18500 <= run && run < 21500", DATA);
    Define("is2025Period", "false", ASIMOV);
    Define("is2026Period", "run >= 21500", DATA);
    Define("is2026Period", "false", ASIMOV);
    Define("isDeadVetoNuRun", "run == 20667 || run == 20668 || run == 20675 || run == 20677", DATA);
    Define("isDeadVetoNuRun", "false", ASIMOV);
    Define("isBrokenPsP0013Run", hasNativeReducedCharge ? "false" : "(19413 <= run && run <= 20142)", DATA);
    Define("isBrokenPsP0013Run", "false", ASIMOV);
    Define("Preshower0_charge_eff", "(isBrokenPsP0013Run && Preshower0_charge <= 0.0f) ? (0.928f * Preshower0_raw_charge) : Preshower0_charge", DATA);
    Define("Preshower0_charge_eff", "Preshower0_charge", ASIMOV);
    Define("Preshower1_charge_eff", "(isBrokenPsP0013Run && Preshower1_charge <= 0.0f) ? (0.928f * Preshower1_raw_charge) : Preshower1_charge", DATA);
    Define("Preshower1_charge_eff", "Preshower1_charge", ASIMOV);

    // Scintillator status flags (data only; used by the built-in GoodScintillatorStatus)
    if (!isMC) {
        Define("BadVetoStatus", "Veto20_status == 528 || Veto21_status == 528", DATA);
        Define("GoodVetoNuStatus", "((VetoNu0_status == 0 || VetoNu0_status == 1) && (VetoNu1_status == 0 || VetoNu1_status == 1)) || (VetoNu0_status == 0 && VetoNu1_status == 16)", DATA);
    }

    // ── VetoNu reduced charge ─────────────────────────────────────────────
    // Priority: 1) aux (waveform) NTuples, 2) branches already in the input NTuple, 3) stop with an error.
    // --no-reduced-charge skips all of this and the VetoNu veto uses the raw charge instead.
    // TODO: once definitions/cuts/histograms are configurable, only load the reduced charge
    //       if something actually depends on it.

    if (!useReducedCharge) {
        m_reducedChargeSource = ReducedChargeSource::None;
        INFO("Reduced charge disabled (--no-reduced-charge): VetoNu veto will use the raw charge.");
    } else if (m_auxChainSet) {
        m_reducedChargeSource = ReducedChargeSource::Aux;
        if (hasNativeReducedCharge) {
            WARNING("Input NTuple already contains VetoNu*_reduced_charge, but aux files were provided: the aux values take priority and will overwrite them.");
        }
        INFO("Reduced charge source: aux (waveform) NTuples.");
        defineReducedChargeFromAux();
    } else if (hasNativeReducedCharge) {
        m_reducedChargeSource = ReducedChargeSource::Native;
        INFO("Reduced charge source: branches in the input NTuple.");
        if (!isMC) {
            WARNING("Collision data is using native NTuple VetoNu*_reduced_charge without aux waveform override; ensure file_config_run3.yaml is passed for calibrated Run 3 reduced charge.");
        }
    } else {
        ERROR("The selection uses the VetoNu reduced charge, but no aux (waveform) files were provided and the input NTuple has no VetoNu*_reduced_charge branches.");
        ERROR("Either add 'waveform_paths' for this run to the file config, or run with --no-reduced-charge to veto on the raw VetoNu charge.");
        throw std::runtime_error("Reduced charge not available");
    }


    defineGRLTimeColumns();  // GoodTimes / ExcludedTimes (data only)

    if (m_timingCalib) {
        if (isMC) {
            setupMCTimingCompatibility();
        }
        defineTimingCalibrationColumns(hasNativeVeto11, hasPreshower23, hasMuon);
    }

    // ── Definitions from config/definitions.yaml ────────────────────────────
    // After all built-in columns, so they can use them (period flags, reduced charge, GoodTimes, ...)
    applyDefinitions();

    // Summary of all added columns (full list with -v)
    std::map<std::string, int> perOrigin;
    for (const auto& r : m_definitionLog) perOrigin[r.origin]++;
    std::string summary;
    for (const auto& [origin, n] : perOrigin) summary += (summary.empty() ? "" : ", ") + std::to_string(n) + " " + origin;
    INFO("Added ", m_definitionLog.size(), " columns: ", summary, ".");
    for (const auto& r : m_definitionLog) DEBUG("  ", r.kind, " ", r.name, " = ", r.expression, "  [", r.dataType, ", ", r.origin, "]");


    // This needs to go at the end of all the definitions, otherwise the aux columns won't be available for cuts
    m_eventIDNode = m_node;
}

// Load the reduced VetoNu charge from the aux (waveform) NTuples via an eventID lookup,
// and define the columns needed to decide whether to trust it (with raw-charge fallback)
void Analysis::defineReducedChargeFromAux() {
    // Capture whether the main PHYS NTuple natively had reduced charge before Redefine()
    // (distinguishes 2025/p0013 vs 2025/p0014 for broken Preshower localtime runs 19413..20142).
    const bool hasNativeRedQ = isColumnDefined("VetoNu0_reduced_charge") && isColumnDefined("VetoNu1_reduced_charge");

    // Build a lookup map from the aux chain manually
    // Key: ((uint64_t)run << 32) | (uint32_t)event, Value: struct of aux quantities
    struct AuxData { float charge35_nu0; float charge35_nu1; };

    auto auxMap = std::make_shared<std::unordered_map<uint64_t, AuxData>>();

    Int_t  run, evt;
    float charge35_nu0, charge35_nu1;

    // Only read the four branches we need (GetEntry would otherwise decompress every branch)
    m_auxChain->SetBranchStatus("*", false);
    for (const char* b : {"run", "event", "myVetoNu0_rawCharge35", "myVetoNu1_rawCharge35"}) {
        m_auxChain->SetBranchStatus(b, true);
    }

    m_auxChain->SetBranchAddress("run",                   &run);
    m_auxChain->SetBranchAddress("event",                 &evt);
    m_auxChain->SetBranchAddress("myVetoNu0_rawCharge35", &charge35_nu0);
    m_auxChain->SetBranchAddress("myVetoNu1_rawCharge35", &charge35_nu1);

    Long64_t nAux = m_auxChain->GetEntries();
    if (nAux == 0) {
        ERROR("Warning: Aux chain has no entries. Check aux file paths and tree name.");
        throw std::runtime_error("Unable to open aux files.");
    }
    auxMap->reserve(static_cast<size_t>(nAux));
    INFO("Loading ", nAux, " aux entries into lookup map...");
    for (Long64_t i = 0; i < nAux; ++i) {
        m_auxChain->GetEntry(i);
        const uint64_t key = getLookupKey(run, evt);

        if (auxMap->find(key) != auxMap->end()) {
            ERROR("Warning: Duplicate (run, event) pair in aux chain: (", run, ", ", evt, "). Overwriting previous entry.");
        }

        (*auxMap)[key] = {charge35_nu0, charge35_nu1};
    }

    INFO("Loaded ", auxMap->size(), " unique (run, event) pairs.");
    m_auxChain->ResetBranchAddresses(); // the addresses above point to local variables

    // Inject aux quantities as new columns via Define()
    // Capture auxMap by shared_ptr so it stays alive.
    // Veto status bit 512 denotes a valid hit on the second digitizer (CaloNu period specific).
    Define("GoodVeto20Hit",     [](int status) { return (status & ~512) == 0; }, {"Veto20_status"});
    Define("GoodVeto21Hit",     [](int status) { return (status & ~512) == 0; }, {"Veto21_status"});
    Define("GoodPreshower0Hit", [](int status) { return (status & ~512) == 0; }, {"Preshower0_status"});
    Define("GoodPreshower1Hit", [](int status) { return (status & ~512) == 0; }, {"Preshower1_status"});
    if (isColumnDefined("Timing0_status") && isColumnDefined("Timing1_status") &&
        isColumnDefined("Timing2_status") && isColumnDefined("Timing3_status")) {
        Define("GoodTimingHit",
            [](int s0, int s1, int s2, int s3) {
                return ((s0 & ~512) == 0) || ((s1 & ~512) == 0) ||
                       ((s2 & ~512) == 0) || ((s3 & ~512) == 0);
            },
            {"Timing0_status", "Timing1_status", "Timing2_status", "Timing3_status"});
    } else {
        Define("GoodTimingHit", "false");
    }

    Define("TimingOK",
        [hasNativeRedQ](Int_t runNum, bool v20, bool v21, bool ps0, bool ps1, bool trig) -> bool {
            if (runNum < 18500) {
                // 2022-2024 Ben Wilson waveform files use Veto2 and Preshower0/1 only
                return v20 || v21 || ps0 || ps1;
            }
            // 2025-2026 raw_reduced_charge_dumper uses Veto2 -> Preshower0/1 -> Timing0..3,
            // skipping broken Preshower localtime on 2025/p0013 runs 19413..20142.
            const bool brokenP0013PS = (!hasNativeRedQ) && (runNum >= 19413 && runNum <= 20142);
            return v20 || v21 || trig || (!brokenP0013PS && (ps0 || ps1));
        },
        {"run", "GoodVeto20Hit", "GoodVeto21Hit", "GoodPreshower0Hit", "GoodPreshower1Hit", "GoodTimingHit"});
    if (!isMC) Define("GoodScintillatorStatus", "TimingOK && GoodVetoNuStatus && !BadVetoStatus", DATA);

    // If the input also has native reduced-charge branches, Redefine them with the aux values
    auto defineOrRedefine = [this](const std::string& name, auto f, const ROOT::RDF::ColumnNames_t& cols) {
        if (isColumnDefined(name)) Redefine(name, f, cols, "aux reduced charge");
        else                       Define(name, f, cols, ALL, "aux reduced charge");
    };

    auto makeLookupFn = [this, auxMap](bool isLayer0) {
        return [this, auxMap, isLayer0](Int_t runNum, Int_t eventID, Int_t longTracks,
                                        bool TimingOK, float rawCharge) -> float {
            const uint64_t key = getLookupKey(runNum, eventID);
            const auto it = auxMap->find(key);
            if (it != auxMap->end()) {
                const float reduced_charge = isLayer0 ? it->second.charge35_nu0 : it->second.charge35_nu1;
                // Stage T6 audit on run 11613 proved exact 0.0f aux reduced-charge on MIP muons (rawCharge > 30 pC)
                // occurs in both Waveforms-2023 (e.g. ev 23803299 when Veto2 saturates) and 2024 aux files.
                const bool isZeroBug = (reduced_charge == 0.0f) && (rawCharge > 30.0f);
                if (!TimingOK || std::isnan(reduced_charge) || isZeroBug) {
                    return -1.0f;
                }
                return std::max(reduced_charge, 0.0f);
            }
            if (longTracks <= 0) {
                return -1.0f;
            }
            ERROR("Warning: Missing aux data for eventID ", eventID, " in run ", runNum,
                  " (longTracks=", longTracks, "). Setting reduced charge to -99999.");
            if (isLayer0) m_NVetoNu0_missing_aux++;
            else          m_NVetoNu1_missing_aux++;
            return -99999.f;
        };
    };

    defineOrRedefine("VetoNu0_reduced_charge", makeLookupFn(true),
                     {"run", "eventID", "longTracks", "TimingOK", "VetoNu0_raw_charge"});
    defineOrRedefine("VetoNu1_reduced_charge", makeLookupFn(false),
                     {"run", "eventID", "longTracks", "TimingOK", "VetoNu1_raw_charge"});

    Define("AuxLookupSuccess", [auxMap, this](Int_t runNum, Int_t eventID, Int_t longTracks) -> bool {
        if (longTracks <= 0) return true;
        return auxMap->count(getLookupKey(runNum, eventID)) > 0;
    }, {"run", "eventID", "longTracks"});

    Define("validReducedVetoNu0Charge", "AuxLookupSuccess && VetoNu0_reduced_charge >= 0");
    Define("validReducedVetoNu1Charge", "AuxLookupSuccess && VetoNu1_reduced_charge >= 0");

    Define("fallbackVetoNu0Charge",
        [this](bool validReducedVetoNu0Charge, float VetoNu0_raw_charge) -> float {
            if (!validReducedVetoNu0Charge) {
                m_NVetoNu0_fallbacks++;
                return VetoNu0_raw_charge;
            }
            return -1234.f; // Return -1234.f to indicate no fallback needed
        }, {"validReducedVetoNu0Charge", "VetoNu0_raw_charge"});

    Define("fallbackVetoNu1Charge",
        [this](bool validReducedVetoNu1Charge, float VetoNu1_raw_charge) -> float {
            if (!validReducedVetoNu1Charge) {
                m_NVetoNu1_fallbacks++;
                return VetoNu1_raw_charge;
            }
            return -1234.f; // Return -1234.f to indicate no fallback needed
        }, {"validReducedVetoNu1Charge", "VetoNu1_raw_charge"});

}

namespace {
    // Column `target` that returns `source` and counts how often it is evaluated.
    // Typed (compiled) Define, so it needs the exact column type.
    template <typename T>
    void defineCountedFallback(Analysis& analysis, const std::string& target, const std::string& source,
                               std::shared_ptr<std::atomic<ULong64_t>> counter, const std::string& origin) {
        analysis.Define(target,
            [counter](T value) { counter->fetch_add(1, std::memory_order_relaxed); return value; },
            {source}, ALL, origin);
    }
}

// Backwards compatibility with older NTuples:
//  1) Old NTuples name the veto scintillator branches VetoSt<N>_<var> instead of Veto<N>_<var>.
//     Every VetoSt<N>_<var> gets an alias Veto<N>_<var>, so the code can always use the new names.
//  2) Veto11 was not read out in 2022-2023 (no free digitiser channel).
//    If the input has no Veto11_* branches at all, every Veto11_<var> is defined
//     as the corresponding Veto10_<var>. Its use is counted, and reportColumnFallbacks() prints a
//     warning at the end of the job for every Veto11 column that was actually used.
void Analysis::setupVetoCompatibility() {
    // 1) VetoSt<N>_<var> -> Veto<N>_<var>
    const std::regex oldVetoName(R"(^VetoSt(\d+)_(.+)$)");
    std::vector<std::string> aliased;
    for (const auto& col : m_node->GetColumnNames()) {
        std::smatch m;
        if (!std::regex_match(col, m, oldVetoName)) continue;
        const std::string newName = "Veto" + m[1].str() + "_" + m[2].str();
        if (isColumnDefined(newName)) continue;
        Alias(newName, col, "Veto compatibility (old VetoSt naming)");
        aliased.push_back(col + " -> " + newName);
    }
    if (!aliased.empty()) {
        INFO("Old NTuple naming: aliased ", aliased.size(), " VetoSt* branches to the Veto* names (e.g. ", aliased.front(), ").");
        for (const auto& a : aliased) DEBUG("  alias: ", a);
    }

    // 2) Veto11 -> Veto10 fallback if the input has no Veto11 branches
    const auto columns = m_node->GetColumnNames();  // includes the aliases above
    const bool hasVeto11 = std::any_of(columns.begin(), columns.end(),
                                       [](const std::string& c) { return c.rfind("Veto11_", 0) == 0; });
    if (hasVeto11) return;

    std::size_t nVeto11 = 0;
    for (const auto& source : columns) {
        if (source.rfind("Veto10_", 0) != 0) continue;
        addCountedFallback("Veto11_" + source.substr(7), source,
                           "Veto compatibility (Veto11 fallback)", "no Veto11 in 2022-2023");
        ++nVeto11;
    }

    if (nVeto11 > 0) {
        INFO("No Veto11 branches in the input (Veto11 was not read out in 2022-2023): ", nVeto11,
             " Veto11_* columns will fall back to the Veto10_* values if used. A warning is printed at the end if they are.");
    }
}

// Define `target` as a counted copy of `source` (see ColumnFallback)
void Analysis::addCountedFallback(const std::string& target, const std::string& source,
                                  const std::string& origin, const std::string& reason) {
    const std::string type = m_node->GetColumnType(source);
    auto counter = std::make_shared<std::atomic<ULong64_t>>(0);

    if      (type == "Float_t"  || type == "float")  defineCountedFallback<Float_t >(*this, target, source, counter, origin);
    else if (type == "Double_t" || type == "double") defineCountedFallback<Double_t>(*this, target, source, counter, origin);
    else if (type == "Int_t"    || type == "int")    defineCountedFallback<Int_t   >(*this, target, source, counter, origin);
    else if (type == "UInt_t"   || type == "unsigned int") defineCountedFallback<UInt_t>(*this, target, source, counter, origin);
    else if (type == "Bool_t"   || type == "bool")   defineCountedFallback<Bool_t  >(*this, target, source, counter, origin);
    else {
        // Unexpected type: plain copy, use not counted
        Define(target, source, ALL, origin);
        counter = nullptr;
    }
    m_columnFallbacks.push_back({target, source, reason, counter});
}

// 2024 dual calorimeter readout: from 2024 the calorimeter PMTs are read out with a low- and a
// high-gain channel, CaloLo<N>_<var> / CaloHi<N>_<var> (and CaloLo_total_<var> / CaloHi_total_<var>),
// instead of the single readout Calo<N>_<var> / Calo_total_<var> of earlier data (and of the MC).
// If the input has CaloLo branches but no single-readout Calo branches, every Calo..._<var> is
// defined as the corresponding CaloLo..._<var> (the low-gain readout stands in for the single
// readout). Its use is counted, and a warning is printed at the end of the job for every
// Calo column that was actually used.
void Analysis::setupCaloCompatibility() {
    const auto columns = m_node->GetColumnNames();
    const std::regex singleReadout(R"(^Calo(\d+|_total)_.+$)");   // Calo0_charge, Calo_total_E_EM (not CaloNu*, CaloLo*, CaloHi*)
    const std::regex loReadout(R"(^CaloLo(\d+|_total)_(.+)$)");    // CaloLo0_charge, CaloLo_total_E_EM

    const bool hasSingleReadout = std::any_of(columns.begin(), columns.end(),
                                              [&](const std::string& c) { return std::regex_match(c, singleReadout); });
    if (hasSingleReadout) return;

    std::vector<std::string> added;
    for (const auto& source : columns) {
        std::smatch m;
        if (!std::regex_match(source, m, loReadout)) continue;
        const std::string target = "Calo" + m[1].str() + "_" + m[2].str();
        if (isColumnDefined(target)) continue;
        addCountedFallback(target, source, "Calo compatibility (2024 CaloLo readout)",
                           "2024 dual calorimeter readout, CaloLo stands in for Calo");
        added.push_back(source + " -> " + target);
    }
    if (!added.empty()) {
        INFO("2024 dual calorimeter readout (CaloLo/CaloHi) and no single-readout Calo branches: ", added.size(),
             " Calo* columns will use the CaloLo values if used (e.g. ", added.front(), "). A warning is printed at the end if they are.");
    }
}

// Warn about every fallback column that was actually used in the event loop
void Analysis::reportColumnFallbacks() const {
    for (const auto& fb : m_columnFallbacks) {
        if (!fb.nUsed) {
            WARNING("'", fb.target, "' is not in the input NTuple (", fb.reason, ") and was defined as '", fb.source,
                    "' (use not counted for this column type).");
        } else if (fb.nUsed->load() > 0) {
            WARNING("'", fb.target, "' is not in the input NTuple (", fb.reason, "): '", fb.source,
                    "' was used instead for ", fb.nUsed->load(), " events.");
        }
    }
}

// Columns written to the output nt tree, from the output columns config (all columns if no config set)
std::vector<std::string> Analysis::selectOutputColumns() {
    auto allColumns = m_node->GetColumnNames();
    const std::set<std::string> internalTiming(m_internalTimingColumns.begin(), m_internalTimingColumns.end());
    if (!internalTiming.empty()) {
        allColumns.erase(
            std::remove_if(allColumns.begin(), allColumns.end(),
                           [&](const std::string& c) { return internalTiming.count(c) > 0; }),
            allColumns.end());
    }
    if (!m_outputColumnsConfig) {
        INFO("No output columns config set: saving all ", allColumns.size(), " columns to ", m_mainFileTreeName, ".");
        return allColumns;
    }
    // Fallback columns (e.g. Veto11 -> Veto10) are compatibility shims, not real branches or framework
    // variables: they are never included by the save_all_* switches, only if a keep entry asks for them
    std::vector<std::string> fallbackColumns = m_internalTimingColumns;
    for (const auto& fb : m_columnFallbacks) fallbackColumns.push_back(fb.target);
    const auto columns = ConfigUtils::selectOutputColumns(allColumns, m_node->GetDefinedColumnNames(), *m_outputColumnsConfig, isMC, fallbackColumns);
    INFO("Saving ", columns.size(), " of ", allColumns.size(), " columns to ", m_mainFileTreeName,
         " (config: ", m_outputColumnsConfig->sourcePath, "). Use -v to list them.");
    for (const auto& c : columns) DEBUG("  saving column: ", c);
    return columns;
}

void replaceAll(std::string& str, const std::string& from, const std::string& to) {
    if (from.empty()) return;
    size_t pos = 0;
    while ((pos = str.find(from, pos)) != std::string::npos) {
        str.replace(pos, from.length(), to);
        pos += to.length();
    }
}

void Analysis::applyCut(std::string cutExpression, std::string cutName, DataType dataType) {

    if (!appliesTo(dataType)) {
        INFO("Skipping cut for ", (isAsimov ? "Asimov" : (isMC ? "MC" : "data")), ": ", cutName);
        return;
    }

    INFO("Applying cut: ", cutName, " (", cutExpression, ")");

    std::string pass_cut_name = "passed_" + cutName;
    const std::vector<std::pair<std::string, std::string>> replacements = {
        {"<=", "leq"}, {">=", "geq"}, {"==", "eq"}, {"=", "eq"},
        {"<",  "lt"},  {">",  "gt"},
        {" ",  "_"}, {"&&", "and"}, {"||", "or"}, {"&", "and"}, {"|", "or"}, {"!", "not"},
        {"(", ""}, {")", ""}, {".", "_"}, {"/", "_"}, {"\\", "_"}, {"[", "_"}, {"]", "_"}, 
        {"-", "minus"}, {"+", "plus"}, {"*", "times"}, {"%", "percent"}, {"^", "caret"}
    };

    for (const auto& [from, to] : replacements) {
        replaceAll(pass_cut_name, from, to);
    }
    
    if (std::find(m_passedCutColNames.begin(), m_passedCutColNames.end(), pass_cut_name) != m_passedCutColNames.end()) {
        throw std::runtime_error("Cut name '" + cutName + "' gives the eventID_pass flag '" + pass_cut_name +
                                 "', which is already used by another cut. Please rename one of the cuts.");
    }
    m_passedCutColNames.push_back(pass_cut_name);
    m_eventIDNode = m_eventIDNode->Define(pass_cut_name, cutExpression);
    
    m_node = m_node->Filter(cutExpression, cutName);

}

namespace {

using RawInputArray = std::array<TimingCalib::RawChannelInput, TimingCalib::kNumChannels>;

struct TimingEventSummary {
    TimingCalib::EventTimingOutput evt;
    TimingCalib::DownstreamRefResult down;
    TimingCalib::SpeedFitResult speed;
    TimingCalib::BackwardHypoResult back;
};

void extractLeadPos(const ROOT::VecOps::RVec<double>& tkPz,
                    const ROOT::VecOps::RVec<double>& tkX,
                    const ROOT::VecOps::RVec<double>& tkY,
                    double& xOut,
                    double& yOut,
                    bool& validOut) {
    xOut = 999999.0;
    yOut = 999999.0;
    validOut = false;
    if (tkPz.empty()) return;
    const long idx = static_cast<long>(ROOT::VecOps::ArgMax(tkPz));
    if (idx < 0 || idx >= static_cast<long>(tkX.size()) || idx >= static_cast<long>(tkY.size())) return;
    const double x = tkX[idx];
    const double y = tkY[idx];
    if (!std::isfinite(x) || !std::isfinite(y) || std::abs(x) >= 1000.0 || std::abs(y) >= 1000.0) return;
    xOut = x;
    yOut = y;
    validOut = true;
}

void attachSingleChannel(Analysis& owner,
                         TimingCalib::TimingChannel ch,
                         const std::string& prefix,
                         const std::string& xCol,
                         const std::string& yCol,
                         const std::string& origin) {
    const int chIdx = static_cast<int>(ch);
    owner.Redefine("_timing_raw_inputs",
        [chIdx](const RawInputArray& prev,
                Int_t st, Float_t bcid, Float_t trig, Float_t loc, Float_t qRaw, Float_t width,
                const ROOT::VecOps::RVec<double>& tkPz,
                const ROOT::VecOps::RVec<double>& tkX,
                const ROOT::VecOps::RVec<double>& tkY) -> RawInputArray {
            RawInputArray out = prev;
            auto& slot = out[chIdx];
            slot.present = true;
            slot.goodStatus = TimingCalib::TimingCalibrator::isGoodWaveformStatus(st);
            slot.bcidTime = static_cast<double>(bcid);
            slot.triggerTime = static_cast<double>(trig);
            slot.localTime = static_cast<double>(loc);
            slot.rawCharge = static_cast<double>(qRaw);
            slot.width = static_cast<double>(width);
            extractLeadPos(tkPz, tkX, tkY, slot.xMm, slot.yMm, slot.validPos);
            return out;
        },
        {"_timing_raw_inputs",
         prefix + "_status", prefix + "_bcidtime", prefix + "_triggertime",
         prefix + "_localtime", prefix + "_raw_charge", prefix + "_width",
         "Track_pz0", xCol, yCol},
        origin);
}

void attachSingleChannelMC(Analysis& owner,
                           TimingCalib::TimingChannel ch,
                           const std::string& prefix,
                           const std::string& xCol,
                           const std::string& yCol,
                           const std::string& origin) {
    const int chIdx = static_cast<int>(ch);
    owner.Redefine("_timing_raw_inputs",
        [chIdx](const RawInputArray& prev,
                Int_t st, Float_t loc, Float_t qRaw, Float_t width,
                const ROOT::VecOps::RVec<double>& tkPz,
                const ROOT::VecOps::RVec<double>& tkX,
                const ROOT::VecOps::RVec<double>& tkY) -> RawInputArray {
            RawInputArray out = prev;
            auto& slot = out[chIdx];
            slot.present = true;
            slot.goodStatus = TimingCalib::TimingCalibrator::isGoodWaveformStatus(st);
            slot.localTime = static_cast<double>(loc);
            slot.rawCharge = static_cast<double>(qRaw);
            slot.width = static_cast<double>(width);
            extractLeadPos(tkPz, tkX, tkY, slot.xMm, slot.yMm, slot.validPos);
            return out;
        },
        {"_timing_raw_inputs",
         prefix + "_status", prefix + "_localtime",
         prefix + "_raw_charge", prefix + "_width",
         "Track_pz0", xCol, yCol},
        origin);
}

void attachTimingPair(Analysis& owner,
                      TimingCalib::TimingChannel ch,
                      const std::string& prefix0,
                      const std::string& prefix1,
                      const std::string& origin) {
    const int chIdx = static_cast<int>(ch);
    owner.Redefine("_timing_raw_inputs",
        [chIdx](const RawInputArray& prev,
                Int_t st0, Float_t bcid0, Float_t trig0, Float_t loc0, Float_t q0, Float_t w0,
                Int_t st1, Float_t bcid1, Float_t trig1, Float_t loc1, Float_t q1, Float_t w1,
                const ROOT::VecOps::RVec<double>& tkPz,
                const ROOT::VecOps::RVec<double>& tkX,
                const ROOT::VecOps::RVec<double>& tkY) -> RawInputArray {
            RawInputArray out = prev;
            double xMm = 999999.0, yMm = 999999.0;
            bool validPos = false;
            extractLeadPos(tkPz, tkX, tkY, xMm, yMm, validPos);
            out[chIdx] = TimingCalib::TimingCalibrator::combineTimingPair(
                TimingCalib::TimingCalibrator::isGoodWaveformStatus(st0), bcid0, trig0, loc0, q0, w0,
                TimingCalib::TimingCalibrator::isGoodWaveformStatus(st1), bcid1, trig1, loc1, q1, w1,
                xMm, yMm, validPos);
            return out;
        },
        {"_timing_raw_inputs",
         prefix0 + "_status", prefix0 + "_bcidtime", prefix0 + "_triggertime",
         prefix0 + "_localtime", prefix0 + "_raw_charge", prefix0 + "_width",
         prefix1 + "_status", prefix1 + "_bcidtime", prefix1 + "_triggertime",
         prefix1 + "_localtime", prefix1 + "_raw_charge", prefix1 + "_width",
         "Track_pz0", "Track_X_atTrig", "Track_Y_atTrig"},
        origin);
}

void attachTimingPairMC(Analysis& owner,
                        TimingCalib::TimingChannel ch,
                        const std::string& prefix0,
                        const std::string& prefix1,
                        const std::string& origin) {
    const int chIdx = static_cast<int>(ch);
    owner.Redefine("_timing_raw_inputs",
        [chIdx](const RawInputArray& prev,
                Int_t st0, Float_t loc0, Float_t q0, Float_t w0,
                Int_t st1, Float_t loc1, Float_t q1, Float_t w1,
                const ROOT::VecOps::RVec<double>& tkPz,
                const ROOT::VecOps::RVec<double>& tkX,
                const ROOT::VecOps::RVec<double>& tkY) -> RawInputArray {
            RawInputArray out = prev;
            double xMm = 999999.0, yMm = 999999.0;
            bool validPos = false;
            extractLeadPos(tkPz, tkX, tkY, xMm, yMm, validPos);
            out[chIdx] = TimingCalib::TimingCalibrator::combineTimingPairMC(
                TimingCalib::TimingCalibrator::isGoodWaveformStatus(st0), loc0, q0, w0,
                TimingCalib::TimingCalibrator::isGoodWaveformStatus(st1), loc1, q1, w1,
                xMm, yMm, validPos);
            return out;
        },
        {"_timing_raw_inputs",
         prefix0 + "_status", prefix0 + "_localtime", prefix0 + "_raw_charge", prefix0 + "_width",
         prefix1 + "_status", prefix1 + "_localtime", prefix1 + "_raw_charge", prefix1 + "_width",
         "Track_pz0", "Track_X_atTrig", "Track_Y_atTrig"},
        origin);
}

} // namespace

void Analysis::setTimingCalibration(const std::string& calibDir) {
    auto cal = std::make_shared<TimingCalib::TimingCalibrator>();
    cal->loadFromDirectory(calibDir);
    m_timingCalib = std::move(cal);
    INFO("Loaded Stage T1/T2 scintillator timing calibration from ", calibDir);
}

void Analysis::setupMCTimingCompatibility() {
    const std::array<const char*, 16> prefixes = {{
        "VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21",
        "Timing0", "Timing1", "Timing2", "Timing3",
        "Preshower0", "Preshower1", "Preshower2", "Preshower3",
        "Muon0", "Muon1"
    }};
    std::vector<std::string> aliased;
    for (const char* p : prefixes) {
        const std::string pfx(p);
        const std::string locName = pfx + "_localtime";
        const std::string oldName = pfx + "_time";
        if (!isColumnDefined(locName) && isColumnDefined(oldName)) {
            Alias(locName, oldName, "MC timing compatibility (old *_time naming)");
            aliased.push_back(oldName + " -> " + locName);
        }
    }
    if (!aliased.empty()) {
        INFO("MC timing compatibility: aliased ", aliased.size(), " *_time branches to *_localtime (e.g. ", aliased.front(), ").");
    }
}

void Analysis::defineTimingCalibrationColumns(bool hasNativeVeto11, bool hasPreshower23, bool hasMuon) {
    const std::string origin = isMC ? "timing calibration (Stage T2)" : "timing calibration (Stage T1)";
    if (!isMC) {
        if (!isColumnDefined("VetoNu0_bcidtime") || !isColumnDefined("VetoNu0_triggertime")) {
            WARNING("TimingCalibration: DATA input lacks *_bcidtime / *_triggertime branches; skipping calibrated timing columns.");
            return;
        }
    } else {
        if (!isColumnDefined("VetoNu0_localtime")) {
            WARNING("TimingCalibration: MC input lacks *_localtime (*_time) branches; skipping calibrated timing columns.");
            return;
        }
        if (!m_timingCalib->hasMcCalib()) {
            WARNING("TimingCalibration: mc_timing_calib.json not loaded; skipping MC timing columns.");
            return;
        }
    }

    Define("_timing_raw_inputs",
        [](Int_t) -> RawInputArray { return RawInputArray{}; },
        {"run"}, ALL, origin);
    m_internalTimingColumns.push_back("_timing_raw_inputs");

    struct SingleSpec {
        TimingCalib::TimingChannel ch;
        const char* prefix;
        const char* xCol;
        const char* yCol;
        bool present;
    };
    const std::vector<SingleSpec> singles = {
        {TimingCalib::TimingChannel::VetoNu0,    "VetoNu0",    "Track_X_atVetoNu",       "Track_Y_atVetoNu",       true},
        {TimingCalib::TimingChannel::VetoNu1,    "VetoNu1",    "Track_X_atVetoNu",       "Track_Y_atVetoNu",       true},
        {TimingCalib::TimingChannel::Veto10,     "Veto10",     "Track_X_atVetoStation1", "Track_Y_atVetoStation1", true},
        {TimingCalib::TimingChannel::Veto11,     "Veto11",     "Track_X_atVetoStation1", "Track_Y_atVetoStation1", hasNativeVeto11},
        {TimingCalib::TimingChannel::Veto20,     "Veto20",     "Track_X_atVetoStation2", "Track_Y_atVetoStation2", true},
        {TimingCalib::TimingChannel::Veto21,     "Veto21",     "Track_X_atVetoStation2", "Track_Y_atVetoStation2", true},
        {TimingCalib::TimingChannel::Preshower0, "Preshower0", "Track_X_atPreshower1",   "Track_Y_atPreshower1",   true},
        {TimingCalib::TimingChannel::Preshower1, "Preshower1", "Track_X_atPreshower2",   "Track_Y_atPreshower2",   true},
        {TimingCalib::TimingChannel::Preshower2, "Preshower2", "Track_X_atPreshower1",   "Track_Y_atPreshower1",   hasPreshower23},
        {TimingCalib::TimingChannel::Preshower3, "Preshower3", "Track_X_atPreshower2",   "Track_Y_atPreshower2",   hasPreshower23},
        {TimingCalib::TimingChannel::Muon0,      "Muon0",      "Track_X_atMuon1",        "Track_Y_atMuon1",        hasMuon},
        {TimingCalib::TimingChannel::Muon1,      "Muon1",      "Track_X_atMuon2",        "Track_Y_atMuon2",        hasMuon},
    };

    for (const auto& s : singles) {
        if (!s.present) continue;
        const std::string pfx = s.prefix;
        if (!isColumnDefined(pfx + "_status") || !isColumnDefined(s.xCol) || !isColumnDefined(s.yCol)) {
            continue;
        }
        if (!isMC) {
            if (!isColumnDefined(pfx + "_bcidtime") || !isColumnDefined(pfx + "_triggertime")) continue;
            attachSingleChannel(*this, s.ch, pfx, s.xCol, s.yCol, origin);
        } else {
            if (!isColumnDefined(pfx + "_localtime")) continue;
            attachSingleChannelMC(*this, s.ch, pfx, s.xCol, s.yCol, origin);
        }
    }
    if (!isMC) {
        attachTimingPair(*this, TimingCalib::TimingChannel::Timing01, "Timing0", "Timing1", origin);
        attachTimingPair(*this, TimingCalib::TimingChannel::Timing23, "Timing2", "Timing3", origin);
    } else {
        attachTimingPairMC(*this, TimingCalib::TimingChannel::Timing01, "Timing0", "Timing1", origin);
        attachTimingPairMC(*this, TimingCalib::TimingChannel::Timing23, "Timing2", "Timing3", origin);
    }

    const auto calib = m_timingCalib;
    const bool hasRedQ = (m_reducedChargeSource != ReducedChargeSource::None);
    const std::string q0Col = hasRedQ ? "VetoNu0_reduced_charge" : "VetoNu0_raw_charge";
    const std::string q1Col = hasRedQ ? "VetoNu1_reduced_charge" : "VetoNu1_raw_charge";
    if (!isMC) {
        Define("_timing_evt_summary",
            [calib, hasRedQ](Int_t run, const RawInputArray& inputs, Float_t q0, Float_t q1) -> TimingEventSummary {
                TimingEventSummary s;
                s.evt = calib->calibrateDataEvent(run, inputs, calib->hasTofMaps(), true);
                const auto& t01In = inputs[static_cast<int>(TimingCalib::TimingChannel::Timing01)];
                const auto& t23In = inputs[static_cast<int>(TimingCalib::TimingChannel::Timing23)];
                const double leadYTrig = t01In.validPos ? t01In.yMm
                                                        : (t23In.validPos ? t23In.yMm : std::numeric_limits<double>::quiet_NaN());
                s.down = TimingCalib::TimingCalibrator::fitDownstreamReferenceMode(
                    s.evt, TimingCalib::DownstreamMode::Trimmed3Sigma, leadYTrig, &inputs);
                s.speed = TimingCalib::TimingCalibrator::fitSpeedAndArrival(s.evt);
                const bool act0 = hasRedQ ? ((q0 >= 0.0f) ? (q0 >= 30.0f) : (inputs[0].rawCharge >= 40.0)) : (inputs[0].rawCharge >= 40.0);
                const bool act1 = hasRedQ ? ((q1 >= 0.0f) ? (q1 >= 30.0f) : (inputs[1].rawCharge >= 40.0)) : (inputs[1].rawCharge >= 40.0);
                s.back = TimingCalib::TimingCalibrator::evaluateBackwardHypothesis(s.evt, s.down, act0, act1);
                return s;
            },
            {"run", "_timing_raw_inputs", q0Col, q1Col}, ALL, origin);
    } else {
        Define("_timing_evt_summary",
            [calib, hasRedQ](Int_t run, Int_t eventID, const RawInputArray& inputs, Float_t q0, Float_t q1) -> TimingEventSummary {
                TimingEventSummary s;
                s.evt = calib->calibrateMCEvent(run, static_cast<int64_t>(eventID), inputs, true, true);
                const auto& t01In = inputs[static_cast<int>(TimingCalib::TimingChannel::Timing01)];
                const auto& t23In = inputs[static_cast<int>(TimingCalib::TimingChannel::Timing23)];
                const double leadYTrig = t01In.validPos ? t01In.yMm
                                                        : (t23In.validPos ? t23In.yMm : std::numeric_limits<double>::quiet_NaN());
                s.down = TimingCalib::TimingCalibrator::fitDownstreamReferenceMode(
                    s.evt, TimingCalib::DownstreamMode::Trimmed3Sigma, leadYTrig, &inputs);
                s.speed = TimingCalib::TimingCalibrator::fitSpeedAndArrival(s.evt);
                const bool act0 = hasRedQ ? ((q0 >= 0.0f) ? (q0 >= 30.0f) : (inputs[0].rawCharge >= 40.0)) : (inputs[0].rawCharge >= 40.0);
                const bool act1 = hasRedQ ? ((q1 >= 0.0f) ? (q1 >= 30.0f) : (inputs[1].rawCharge >= 40.0)) : (inputs[1].rawCharge >= 40.0);
                s.back = TimingCalib::TimingCalibrator::evaluateBackwardHypothesis(s.evt, s.down, act0, act1);
                return s;
            },
            {"run", "eventID", "_timing_raw_inputs", q0Col, q1Col}, ALL, origin);
    }
    m_internalTimingColumns.push_back("_timing_evt_summary");

    Define("Timing_anchor_ch", [](const TimingEventSummary& s) { return s.evt.anchorChannel; }, {"_timing_evt_summary"}, ALL, origin);
    Define("t0_down", [](const TimingEventSummary& s) {
        return s.down.valid ? s.down.t0Ns : std::numeric_limits<double>::quiet_NaN();
    }, {"_timing_evt_summary"}, ALL, origin);
    Define("sigma_t0_down", [](const TimingEventSummary& s) {
        return s.down.valid ? s.down.sigmaT0Ns : std::numeric_limits<double>::quiet_NaN();
    }, {"_timing_evt_summary"}, ALL, origin);
    Define("chi2_down", [](const TimingEventSummary& s) {
        return s.down.valid ? s.down.chi2 : std::numeric_limits<double>::quiet_NaN();
    }, {"_timing_evt_summary"}, ALL, origin);
    Define("ndof_down", [](const TimingEventSummary& s) { return s.down.ndof; }, {"_timing_evt_summary"}, ALL, origin);
    Define("n_down_used", [](const TimingEventSummary& s) { return s.down.nUsed; }, {"_timing_evt_summary"}, ALL, origin);

    Define("timing_beta", [](const TimingEventSummary& s) {
        return s.speed.valid ? s.speed.beta : std::numeric_limits<double>::quiet_NaN();
    }, {"_timing_evt_summary"}, ALL, origin);
    Define("timing_sigma_beta", [](const TimingEventSummary& s) {
        return s.speed.valid ? s.speed.sigmaBeta : std::numeric_limits<double>::quiet_NaN();
    }, {"_timing_evt_summary"}, ALL, origin);
    Define("timing_speed_chi2", [](const TimingEventSummary& s) {
        return s.speed.valid ? s.speed.chi2 : std::numeric_limits<double>::quiet_NaN();
    }, {"_timing_evt_summary"}, ALL, origin);
    Define("timing_speed_ndof", [](const TimingEventSummary& s) { return s.speed.ndof; }, {"_timing_evt_summary"}, ALL, origin);

    Define("VetoNu_dt_comb", [](const TimingEventSummary& s) {
        return s.back.valid ? s.back.dtCombNs : std::numeric_limits<double>::quiet_NaN();
    }, {"_timing_evt_summary"}, ALL, origin);
    Define("VetoNu_z_comb", [](const TimingEventSummary& s) {
        return s.back.valid ? s.back.zComb : std::numeric_limits<double>::quiet_NaN();
    }, {"_timing_evt_summary"}, ALL, origin);
    Define("VetoNu_dt10", [](const TimingEventSummary& s) {
        return s.back.dt10Ns;
    }, {"_timing_evt_summary"}, ALL, origin);
    Define("delta_chi2_back", [](const TimingEventSummary& s) {
        return s.back.valid ? s.back.deltaChi2Back : std::numeric_limits<double>::quiet_NaN();
    }, {"_timing_evt_summary"}, ALL, origin);
    Define("VetoNu_charge_asym", [](Float_t q0, Float_t q1) -> double {
        const double a0 = std::max(0.0, static_cast<double>(q0));
        const double a1 = std::max(0.0, static_cast<double>(q1));
        const double sum = a0 + a1;
        return (sum > 0.0) ? ((a1 - a0) / sum) : std::numeric_limits<double>::quiet_NaN();
    }, {q0Col, q1Col}, ALL, origin);

    auto defineVetoNuDiff = [&](int chIdx, const std::string& baseName) {
        Define(baseName + "_dt", [chIdx](const TimingEventSummary& s) {
            const auto& cr = s.evt.channels[chIdx];
            if (!s.down.valid || !cr.valid) return std::numeric_limits<double>::quiet_NaN();
            return cr.tCalNs - s.down.t0Ns;
        }, {"_timing_evt_summary"}, ALL, origin);
        Define(baseName + "_pull", [chIdx](const TimingEventSummary& s) {
            const auto& cr = s.evt.channels[chIdx];
            if (!s.down.valid || !cr.valid) return std::numeric_limits<double>::quiet_NaN();
            const double sig = std::hypot(cr.sigmaCalNs, s.down.sigmaT0Ns);
            return (sig > 0.0) ? ((cr.tCalNs - s.down.t0Ns) / sig) : std::numeric_limits<double>::quiet_NaN();
        }, {"_timing_evt_summary"}, ALL, origin);
    };
    defineVetoNuDiff(static_cast<int>(TimingCalib::TimingChannel::VetoNu0), "VetoNu0");
    defineVetoNuDiff(static_cast<int>(TimingCalib::TimingChannel::VetoNu1), "VetoNu1");

    const auto& meta = TimingCalib::TimingCalibrator::channelMetadata();
    for (int c = 0; c < TimingCalib::kNumChannels; ++c) {
        const std::string cname = meta[c].name;
        Define(cname + "_timing_valid", [c](const TimingEventSummary& s) {
            return s.evt.channels[c].valid;
        }, {"_timing_evt_summary"}, ALL, origin);
        Define(cname + "_t1", [c](const TimingEventSummary& s) {
            return s.evt.channels[c].valid ? s.evt.channels[c].t1Ns : std::numeric_limits<double>::quiet_NaN();
        }, {"_timing_evt_summary"}, ALL, origin);
        Define(cname + "_t2", [c](const TimingEventSummary& s) {
            return s.evt.channels[c].valid ? s.evt.channels[c].t2Ns : std::numeric_limits<double>::quiet_NaN();
        }, {"_timing_evt_summary"}, ALL, origin);
        Define(cname + "_r_unwrap", [c](const TimingEventSummary& s) {
            const auto& cr = s.evt.channels[c];
            return (cr.valid || cr.unwrapFailed) ? cr.rUnwrapNs : std::numeric_limits<double>::quiet_NaN();
        }, {"_timing_evt_summary"}, ALL, origin);
        Define(cname + "_caltime", [c](const TimingEventSummary& s) {
            return s.evt.channels[c].valid ? s.evt.channels[c].tCalNs : std::numeric_limits<double>::quiet_NaN();
        }, {"_timing_evt_summary"}, ALL, origin);
        Define(cname + "_cal_sigma", [c](const TimingEventSummary& s) {
            return s.evt.channels[c].valid ? s.evt.channels[c].sigmaCalNs : std::numeric_limits<double>::quiet_NaN();
        }, {"_timing_evt_summary"}, ALL, origin);
    }

    // Orthogonal blinding lock & Zone A charge definitions for YAML timing selection configs
    Define("Timing_Allow_SR_ZoneB", [](Int_t) -> bool { return false; }, {"run"}, DATA, origin);
    Define("Timing_Allow_SR_ZoneB", [](Int_t) -> bool { return true; }, {"run"}, ASIMOV, origin);
    Define("VetoNu0_zone_a",
        [hasRedQ](Float_t q0, const RawInputArray& inputs) -> bool {
            const double qr = inputs[0].rawCharge;
            return hasRedQ ? ((q0 >= 0.0f) ? (q0 < 30.0f) : (qr < 40.0)) : (qr < 40.0);
        },
        {q0Col, "_timing_raw_inputs"}, ALL, origin);
    Define("VetoNu1_zone_a",
        [hasRedQ](Float_t q1, const RawInputArray& inputs) -> bool {
            const double qr = inputs[1].rawCharge;
            return hasRedQ ? ((q1 >= 0.0f) ? (q1 < 30.0f) : (qr < 40.0)) : (qr < 40.0);
        },
        {q1Col, "_timing_raw_inputs"}, ALL, origin);
}

// Main analysis function that runs the analysis and applies cuts, then saves the output to a file if specified.
void Analysis::Run(TString outputFileName) {

    BuildDataFrame();

    if (!m_df) {
        ERROR("Error: DataFrame not built. Call BuildDataFrame() first.");
        throw std::runtime_error("DataFrame not built");
        return;
    }

    auto nEventsBeforeCuts = m_node->Count();

    // ── Cuts and histograms from the selection config ──────────────────
    applySelection();

    // ── Book ALL actions before triggering any event loop ──────────────────
    // TODO: Move to a Finalise() function
    auto cutReport = m_node->Report();
    // Run range in the input (before any cuts), only used as a sanity check against m_runNumbers.
    // Booked here so it is filled in the same event loop as everything else.
    auto inputRunMin = m_df->Min<int>("run");
    auto inputRunMax = m_df->Max<int>("run");

    if (outputFileName != "") {
        INFO("Saving snapshot to ", outputFileName, "...");

        // Both snapshots are booked lazily so that they are filled in ONE event loop together with
        // the cutflow, histograms and counters booked above.
        // RDataFrame cannot write two trees to the same file in one event loop, so the eventID_pass
        // tree is written to a temporary file next to the output and copied in afterwards
        // (a fast, basket-level copy: no re-reading of the input).
        auto opts = ROOT::RDF::RSnapshotOptions();
        opts.fMode = "RECREATE";
        opts.fLazy = true;
        const auto columns = selectOutputColumns();
        auto ntSnapshot = m_node->Snapshot(m_mainFileTreeName, outputFileName, columns, opts);

        const std::string eventIDTmpFile = std::string(outputFileName.Data()) + ".eventID_pass.tmp.root";
        m_passedCutColNames.push_back("run");
        m_passedCutColNames.push_back("eventID");
        auto eventIDSnapshot = m_eventIDNode->Snapshot("eventID_pass", eventIDTmpFile, m_passedCutColNames, opts);

        // ── THE event loop ──────────────────────────────────────────────────
        INFO("Running the event loop: writing ", columns.size(), " columns to ", m_mainFileTreeName, " and ",
             m_passedCutColNames.size(), " columns to eventID_pass...");
        ntSnapshot.GetValue();       // triggers the (single) event loop
        eventIDSnapshot.GetValue();  // already filled by the same loop

        // ── Post-processing to save metadata and cutflow info ───────────────
        TFile *file = TFile::Open(outputFileName, "UPDATE");

        // ── Metadata tree ────────────────────────────────────────────────────
        // Filled from the run numbers this job was asked to process (m_runNumbers), NOT from the
        // events that pass the cuts, so the lumi is correct even if no events are selected.
        TTree *meta_tree = new TTree("meta", "Metadata tree");

        ULong64_t nEventsInput = nEventsBeforeCuts.GetValue();
        if (m_runNumbers.empty()) {
            WARNING("No run numbers set (Analysis::setRunNumbers). The meta tree will have no runs.");
        }
        if (nEventsInput == 0) {
            WARNING("No events in the input files. The nt tree will be empty.");
        } else {
            // Sanity check: the input files should only contain the requested run(s)
            const std::set<int> requested(m_runNumbers.begin(), m_runNumbers.end());
            if (!requested.count(*inputRunMin) || !requested.count(*inputRunMax)) {
                WARNING("Input files contain run numbers in [", *inputRunMin, ", ", *inputRunMax,
                        "] which are not all in the requested run list. Check the file config!");
            }
        }

        std::vector<int>   runBranch(m_runNumbers.begin(), m_runNumbers.end());
        std::vector<float> lumiBranch;
        for (const auto& run : runBranch) {
            auto it = m_runLumiDict.find(run);
            lumiBranch.push_back(it != m_runLumiDict.end() ? it->second : -1.f);

            if (it == m_runLumiDict.end()) {
                if (isMC) INFO("MC run ", run, " has no GRL lumi. Setting lumi to -1.");
                else      WARNING("Run ", run, " not found in GRL! Setting lumi to -1.");
            }
        }

        float totalLumi = std::accumulate(lumiBranch.begin(), lumiBranch.end(), 0.f);
        INFO("Total integrated luminosity for this job: ", totalLumi, " /pb");

        meta_tree->Branch("run_number",     &runBranch);
        meta_tree->Branch("lumi",           &lumiBranch);
        meta_tree->Branch("n_events_input", &nEventsInput);
        meta_tree->Fill();
        meta_tree->Write();
        INFO("Saved metadata tree with ", runBranch.size(), " run(s).");

        // ── Cutflow tree (uses cached cutReport) ────────────────────────────
        TTree *cutflow_tree = new TTree("cutflow", "Cutflow tree");
        std::string cut_name;
        ULong64_t   all, passed;
        double      efficiency;

        cutflow_tree->Branch("cut_name",   &cut_name);
        cutflow_tree->Branch("all",        &all);
        cutflow_tree->Branch("passed",     &passed);
        cutflow_tree->Branch("efficiency", &efficiency);

        for (auto&& cut : *cutReport) {
            cut_name   = cut.GetName();
            all        = cut.GetAll();
            passed     = cut.GetPass();
            efficiency = cut.GetEff();
            INFO("Cut: ", cut_name, ", All: ", all, ", Passed: ", passed, ", Efficiency: ", efficiency);
            cutflow_tree->Fill();
        }
        cutflow_tree->Write();
        file->Close();
        INFO("Wrote cutflow tree");

        // ── Histograms ────────────────────────────
        if (!m_histResults.empty()) {
            INFO("Writing histograms to file...");
            // make TDirectory for histograms
            TFile *histFile = TFile::Open(outputFileName, "UPDATE");
            histFile->mkdir("histograms");
            histFile->cd("histograms");
            for (auto&& hist : m_histResults) {
                hist->Write();
            }
            histFile->Close();
            INFO("Wrote ", m_histResults.size(), " histograms to file.");
        }

        // ── Event ID pass tree: copy from the temporary file into the output ─
        {
            std::unique_ptr<TFile> tmpFile(TFile::Open(eventIDTmpFile.c_str(), "READ"));
            std::unique_ptr<TFile> outFile(TFile::Open(outputFileName, "UPDATE"));
            if (!tmpFile || tmpFile->IsZombie() || !outFile || outFile->IsZombie()) {
                throw std::runtime_error("Could not open " + eventIDTmpFile + " or " + std::string(outputFileName.Data()) + " to copy the eventID_pass tree");
            }
            auto* eventIDTree = tmpFile->Get<TTree>("eventID_pass");
            if (!eventIDTree) {
                throw std::runtime_error("eventID_pass tree not found in " + eventIDTmpFile);
            }
            outFile->cd();
            TTree* copy = eventIDTree->CloneTree(-1, "fast");
            copy->Write();
            INFO("Wrote eventID_pass tree with ", copy->GetEntries(), " entries.");
            outFile->Close();
            tmpFile->Close();
        }
        std::filesystem::remove(eventIDTmpFile);

    } else {
        cutReport->Print();
    }

    INFO("Total event loop runs: ", m_node->GetNRuns());
    if (m_node->GetNRuns() > 1) {  // should be exactly 1
        WARNING("Event loop ran multiple times. This is inefficient.");
    }

    // Veto11 -> Veto10 and Calo -> CaloLo fallbacks (only reported if used)
    reportColumnFallbacks();

    // Sanity check fallbacks and missing aux data
    // These go here, after event loop has run. If we put them before, they would be printed before the event loop runs and thus always show 0 fallbacks, which is misleading.
    if (m_auxChainSet) {
        INFO("Number of VetoNu0 reduced charge fallbacks: ", m_NVetoNu0_fallbacks.load());
        INFO("Number of VetoNu1 reduced charge fallbacks: ", m_NVetoNu1_fallbacks.load());
        if (m_NVetoNu0_missing_aux.load() > 0) {
            ERROR(m_NVetoNu0_missing_aux.load(), " events had missing VetoNu0 auxiliary data. This should never happen! Fellback to raw charge. Check aux files for missing data or mismatched event IDs.");
        }
        if (m_NVetoNu1_missing_aux.load() > 0) {
            ERROR(m_NVetoNu1_missing_aux.load(), " events had missing VetoNu1 auxiliary data. This should never happen! Fellback to raw charge. Check aux files for missing data or mismatched event IDs.");
        }
    }
}