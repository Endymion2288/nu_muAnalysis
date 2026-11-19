#include <ROOT/TProcessExecutor.hxx>
#include <Compression.h>
#include <TError.h>
#include <TFile.h>
#include <TROOT.h>
#include <TTree.h>

#include <lz4.h>
#include <sqlite3.h>
#include <zlib.h>
#include <zstd.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <mutex>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_set>
#include <vector>

#include <unistd.h>

namespace fs = std::filesystem;

namespace {

constexpr float kNaNF = std::numeric_limits<float>::quiet_NaN();
constexpr uint16_t kStatusCompressed = (1u << 11);
constexpr uint8_t kEventMarker = 0xBB;
constexpr uint8_t kFragmentMarker = 0xAA;
constexpr uint32_t kPMTSourceMask = 0xFFFF0000u;
constexpr uint32_t kPMTSourceId = 0x00040000u;
constexpr uint32_t kWaveInvalidMask = (64u | 128u | 256u);

#pragma pack(push, 1)
struct RawEventHeader {
    uint8_t marker;
    uint8_t event_tag;
    uint16_t trigger_bits;
    uint8_t version_number;
    uint8_t compression_code;
    uint16_t header_size;
    uint32_t payload_size;
    uint8_t fragment_count;
    uint8_t run_number[3];
    uint64_t event_id;
    uint64_t event_counter;
    uint16_t bc_id;
    uint16_t status;
    uint64_t timestamp;
};

struct RawFragmentHeader {
    uint8_t marker;
    uint8_t fragment_tag;
    uint16_t trigger_bits;
    uint16_t version_number;
    uint16_t header_size;
    uint32_t payload_size;
    uint32_t source_id;
    uint64_t event_id;
    uint16_t bc_id;
    uint16_t status;
    uint64_t timestamp;
};
#pragma pack(pop)

static_assert(sizeof(RawEventHeader) == 44, "RawEventHeader must be 44 bytes");
static_assert(sizeof(RawFragmentHeader) == 36, "RawFragmentHeader must be 36 bytes");

struct CondParams {
    double nomTrigNs{200.0};
    double trigOffNs{-35.0};
    double rangeV{2.0};
    int baseLo{62};
    float mvPerBit{2.0f / 16.384f};
};

struct TargetEvent {
    int64_t eventId{0};
    float baseline[2]{0.0f, 0.0f};
    float ntRawCharge[2]{0.0f, 0.0f};
    int32_t vnStatus[2]{0, 0};
    float expectedTime{kNaNF};
    float q35[2]{kNaNF, kNaNF};
    float rawCalc[2]{kNaNF, kNaNF};
    uint8_t fallbackMode{0};
    uint8_t found{0};
};

struct BufferedStream {
    int fd{-1};
    FILE* pipe{nullptr};
    std::vector<uint8_t> buf;
    size_t pos{0};
    size_t end{0};
    bool isSeekable{false};

    explicit BufferedStream(size_t cap = 4 * 1024 * 1024) : buf(cap) {}

    ~BufferedStream() { closeStream(); }

    void closeStream() {
        if (fd >= 0) {
            ::close(fd);
            fd = -1;
        }
        if (pipe) {
            ::pclose(pipe);
            pipe = nullptr;
        }
        pos = 0;
        end = 0;
        isSeekable = false;
    }

    bool openPath(const std::string& path, bool allowXrdFallback = true) {
        closeStream();
        fd = ::open(path.c_str(), O_RDONLY);
        if (fd >= 0) {
            isSeekable = true;
#if defined(POSIX_FADV_SEQUENTIAL)
            ::posix_fadvise(fd, 0, 0, POSIX_FADV_SEQUENTIAL);
#endif
            return true;
        }
        if (!allowXrdFallback) return false;
        std::string url = path;
        if (url.rfind("root://", 0) != 0) {
            if (url.rfind("/eos/experiment/", 0) == 0) {
                url = "root://eospublic.cern.ch/" + url;
            } else if (url.rfind("/eos/user/", 0) == 0 || url.rfind("/eos/home-", 0) == 0) {
                url = "root://eoshome-x.cern.ch/" + url;
            } else {
                return false;
            }
        }
        std::string cmd = "xrdcp -s \"" + url + "\" -";
        pipe = ::popen(cmd.c_str(), "r");
        if (!pipe) return false;
        isSeekable = false;
        return true;
    }

    bool fill() {
        if (pos < end) {
            const size_t rem = end - pos;
            std::memmove(buf.data(), buf.data() + pos, rem);
            pos = 0;
            end = rem;
        } else {
            pos = 0;
            end = 0;
        }
        while (end < buf.size()) {
            ssize_t n = 0;
            if (fd >= 0) {
                n = ::read(fd, buf.data() + end, buf.size() - end);
            } else if (pipe) {
                n = static_cast<ssize_t>(::fread(buf.data() + end, 1, buf.size() - end, pipe));
            } else {
                return false;
            }
            if (n > 0) {
                end += static_cast<size_t>(n);
                return end > 0;
            }
            if (n == 0) {
                return end > 0;
            }
            if (errno == EINTR) continue;
            return end > 0;
        }
        return end > 0;
    }

    bool readExact(uint8_t* dst, size_t nbytes) {
        size_t copied = 0;
        while (copied < nbytes) {
            const size_t avail = end - pos;
            if (avail > 0) {
                const size_t take = std::min(avail, nbytes - copied);
                std::memcpy(dst + copied, buf.data() + pos, take);
                pos += take;
                copied += take;
            } else {
                if (!fill()) return false;
            }
        }
        return true;
    }

    bool skipExact(size_t nbytes) {
        size_t avail = end - pos;
        if (nbytes <= avail) {
            pos += nbytes;
            return true;
        }
        size_t rem = nbytes - avail;
        pos = 0;
        end = 0;
        if (isSeekable && fd >= 0 && rem >= 524288) {
            if (::lseek(fd, static_cast<off_t>(rem), SEEK_CUR) >= 0) {
                return true;
            }
        }
        while (rem > 0) {
            if (!fill()) return false;
            avail = end - pos;
            const size_t take = std::min(avail, rem);
            pos += take;
            rem -= take;
        }
        return true;
    }
};

std::vector<std::string> splitComma(const std::string& s) {
    std::vector<std::string> out;
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ',')) {
        if (!item.empty()) out.push_back(item);
    }
    return out;
}

std::vector<std::string> readLines(const std::string& path) {
    std::ifstream ifs(path);
    if (!ifs.is_open()) throw std::runtime_error("Cannot open list file: " + path);
    std::vector<std::string> out;
    std::string line;
    while (std::getline(ifs, line)) {
        const auto a = line.find_first_not_of(" \t\r\n");
        if (a == std::string::npos || line[a] == '#') continue;
        const auto b = line.find_last_not_of(" \t\r\n");
        out.push_back(line.substr(a, b - a + 1));
    }
    return out;
}

std::string toXrdIfNeeded(const std::string& path) {
    if (path.rfind("root://", 0) == 0) return path;
    if (fs::exists(path)) return path;
    if (path.rfind("/eos/experiment/", 0) == 0) return "root://eospublic.cern.ch/" + path;
    if (path.rfind("/eos/user/", 0) == 0 || path.rfind("/eos/home-", 0) == 0) {
        return "root://eoshome-x.cern.ch/" + path;
    }
    return path;
}

CondParams queryConditions(const std::string& dbPath, int run) {
    CondParams cp;
    if (dbPath.empty() || !fs::exists(dbPath)) {
        cp.baseLo = static_cast<int>((cp.nomTrigNs + cp.trigOffNs) / 2.0) - 20;
        cp.mvPerBit = static_cast<float>(cp.rangeV / 16.384);
        return cp;
    }
    sqlite3* db = nullptr;
    if (sqlite3_open_v2(dbPath.c_str(), &db, SQLITE_OPEN_READONLY, nullptr) != SQLITE_OK) {
        if (db) sqlite3_close(db);
        throw std::runtime_error("Cannot open SQLite DB: " + dbPath);
    }
    const sqlite3_int64 iov = static_cast<sqlite3_int64>(static_cast<uint64_t>(run) << 32);

    auto queryOneDouble = [&](const char* sql, double fallback) -> double {
        sqlite3_stmt* stmt = nullptr;
        if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
            return fallback;
        }
        sqlite3_bind_int64(stmt, 1, iov);
        sqlite3_bind_int64(stmt, 2, iov);
        double val = fallback;
        if (sqlite3_step(stmt) == SQLITE_ROW && sqlite3_column_type(stmt, 0) != SQLITE_NULL) {
            val = sqlite3_column_double(stmt, 0);
        }
        sqlite3_finalize(stmt);
        return val;
    };

    cp.nomTrigNs = queryOneDouble(
        "SELECT NominalTriggerTime FROM CONDBR3_F0023_IOVS "
        "WHERE CHANNEL_ID=0 AND IOV_SINCE <= ?1 AND ?2 < IOV_UNTIL "
        "ORDER BY IOV_SINCE DESC LIMIT 1;",
        200.0);
    cp.trigOffNs = queryOneDouble(
        "SELECT TriggerOffset FROM CONDBR3_F0024_IOVS "
        "WHERE CHANNEL_ID=4 AND IOV_SINCE <= ?1 AND ?2 < IOV_UNTIL "
        "ORDER BY IOV_SINCE DESC LIMIT 1;",
        -35.0);
    cp.rangeV = queryOneDouble(
        "SELECT range FROM CONDBR3_F0022_IOVS "
        "WHERE CHANNEL_ID=4 AND IOV_SINCE <= ?1 AND ?2 < IOV_UNTIL "
        "ORDER BY IOV_SINCE DESC LIMIT 1;",
        2.0);
    sqlite3_close(db);

    cp.baseLo = static_cast<int>((cp.nomTrigNs + cp.trigOffNs) / 2.0) - 20;
    cp.mvPerBit = static_cast<float>(cp.rangeV / 16.384);
    return cp;
}

template <size_t N>
float meanGoodTime(const int32_t (&st)[N], const float (&lt)[N]) {
    size_t n = 0;
    double sum = 0.0;
    for (size_t i = 0; i < N; ++i) {
        if ((st[i] & ~512) != 0) continue;
        double t = static_cast<double>(lt[i]);
        if (!std::isfinite(t)) continue;
        if (st[i] & 512) t += 16.0;
        sum += t;
        ++n;
    }
    return (n > 0) ? static_cast<float>(sum / static_cast<double>(n)) : kNaNF;
}

bool decompressEvent(ZSTD_DCtx* dctx,
                     uint8_t compCode,
                     const uint8_t* src,
                     size_t srcSize,
                     std::vector<uint8_t>& dst,
                     size_t& outLen) {
    if (compCode == 1) {
        const unsigned long long cSize = ZSTD_getFrameContentSize(src, srcSize);
        if (cSize != ZSTD_CONTENTSIZE_ERROR && cSize != ZSTD_CONTENTSIZE_UNKNOWN) {
            if (dst.size() < cSize) dst.resize(static_cast<size_t>(cSize));
            const size_t rc = ZSTD_decompressDCtx(dctx, dst.data(), dst.size(), src, srcSize);
            if (!ZSTD_isError(rc)) {
                outLen = rc;
                return true;
            }
        }
        size_t est = std::max<size_t>(srcSize * 6, 4 * 1024 * 1024);
        for (int retry = 0; retry < 4; ++retry) {
            if (dst.size() < est) dst.resize(est);
            const size_t rc = ZSTD_decompressDCtx(dctx, dst.data(), dst.size(), src, srcSize);
            if (!ZSTD_isError(rc)) {
                outLen = rc;
                return true;
            }
            est *= 2;
        }
        return false;
    }
    if (compCode == 2) {
        uLongf est = static_cast<uLongf>(std::max<size_t>(srcSize * 4, 1024 * 1024));
        for (int retry = 0; retry < 5; ++retry) {
            if (dst.size() < est) dst.resize(est);
            uLongf cap = static_cast<uLongf>(dst.size());
            const int rc = uncompress(dst.data(), &cap, src, static_cast<uLong>(srcSize));
            if (rc == Z_OK) {
                outLen = static_cast<size_t>(cap);
                return true;
            }
            if (rc != Z_BUF_ERROR) return false;
            est *= 2;
        }
        return false;
    }
    if (compCode == 3) {
        size_t est = std::max<size_t>(srcSize * 4, 1024 * 1024);
        for (int retry = 0; retry < 5; ++retry) {
            if (dst.size() < est) dst.resize(est);
            const int rc = LZ4_decompress_safe(
                reinterpret_cast<const char*>(src),
                reinterpret_cast<char*>(dst.data()),
                static_cast<int>(srcSize),
                static_cast<int>(dst.size()));
            if (rc >= 0) {
                outLen = static_cast<size_t>(rc);
                return true;
            }
            est *= 2;
        }
        return false;
    }
    return false;
}

bool processDigitizerPayload(const uint8_t* fragPayload,
                             size_t fragSize,
                             const CondParams& cp,
                             TargetEvent& ev,
                             double& localMaxRawDiff) {
    if (fragSize < 16) return false;
    const uint32_t* words = reinterpret_cast<const uint32_t*>(fragPayload);
    const uint32_t eventSize = words[0] & 0x0FFFFFFFu;
    if (static_cast<size_t>(eventSize) * 4u != fragSize || eventSize < 4u) return false;

    const uint16_t channelMask =
        static_cast<uint16_t>((words[1] & 0x000000FFu) | ((words[2] & 0xFF000000u) >> 16));
    const uint32_t nChActive = static_cast<uint32_t>(__builtin_popcount(channelMask));
    if (nChActive == 0u) return false;
    const uint32_t eventSizeNoHdr = eventSize - 4u;
    if ((eventSizeNoHdr % nChActive) != 0u) return false;

    const uint32_t wordsPerCh = eventSizeNoHdr / nChActive;
    const int nSamples = static_cast<int>(wordsPerCh * 2u);
    if (nSamples <= 0) return false;

    const int lo = std::max(0, cp.baseLo);
    const int hi = std::min(nSamples - 1, cp.baseLo + 100);
    if (hi <= lo) return false;

    for (int idx = 0; idx < 2; ++idx) {
        const int ch = (idx == 0) ? 4 : 5;
        if (((channelMask >> ch) & 1u) == 0u) {
            ev.q35[idx] = kNaNF;
            continue;
        }
        if ((static_cast<uint32_t>(ev.vnStatus[idx]) & kWaveInvalidMask) != 0u) {
            ev.q35[idx] = kNaNF;
            continue;
        }

        const uint32_t prevActive =
            static_cast<uint32_t>(__builtin_popcount(channelMask & ((1u << ch) - 1u)));
        const uint32_t* chWords = words + 4u + prevActive * wordsPerCh;

        float sumRawMv = 0.0f;
        float sumRedMv = 0.0f;
        const bool hasExp = std::isfinite(ev.expectedTime);
        const float expLim = hasExp ? (ev.expectedTime + 35.0f) : -1e9f;
        const float bl = ev.baseline[idx];
        const float scale = cp.mvPerBit;

        for (int s = lo; s <= hi; ++s) {
            const uint32_t w = chWords[s >> 1];
            const uint16_t adc = static_cast<uint16_t>((s & 1) ? ((w >> 16) & 0xFFFFu) : (w & 0xFFFFu));
            const float waveMv = bl - scale * static_cast<float>(adc);
            sumRawMv += waveMv;
            if (hasExp && (2.0f * static_cast<float>(s) < expLim)) {
                sumRedMv += waveMv;
            }
        }
        const float qRaw = sumRawMv * 0.04f;
        ev.rawCalc[idx] = qRaw;
        if (std::isfinite(ev.ntRawCharge[idx])) {
            const double d = std::abs(static_cast<double>(qRaw) - static_cast<double>(ev.ntRawCharge[idx]));
            if (d > localMaxRawDiff) localMaxRawDiff = d;
        }
        ev.q35[idx] = hasExp ? (sumRedMv * 0.04f) : kNaNF;
    }
    return true;
}

bool scanRawFile(const std::string& rawPath,
                 std::vector<TargetEvent>& targets,
                 const CondParams& cp,
                 double& localMaxRawDiff,
                 size_t& matchedInFile,
                 ZSTD_DCtx* dctx,
                 std::vector<uint8_t>& compBuf,
                 std::vector<uint8_t>& decompBuf,
                 BufferedStream& stream) {
    if (!stream.openPath(rawPath, true)) {
        return false;
    }
    RawEventHeader hdr{};
    while (stream.readExact(reinterpret_cast<uint8_t*>(&hdr), sizeof(hdr))) {
        if (hdr.marker != kEventMarker) {
            throw std::runtime_error("Corrupt EventHeader marker in " + rawPath);
        }
        if (hdr.header_size > sizeof(hdr)) {
            if (!stream.skipExact(hdr.header_size - sizeof(hdr))) break;
        }
        const size_t paySize = static_cast<size_t>(hdr.payload_size);
        const int64_t eid = static_cast<int64_t>(hdr.event_counter);

        auto it = std::lower_bound(
            targets.begin(), targets.end(), eid,
            [](const TargetEvent& a, int64_t b) { return a.eventId < b; });
        if (it == targets.end() || it->eventId != eid) {
            if (!stream.skipExact(paySize)) break;
            continue;
        }
        if (!std::isfinite(it->expectedTime)) {
            it->q35[0] = kNaNF;
            it->q35[1] = kNaNF;
            it->found = 1;
            ++matchedInFile;
            if (!stream.skipExact(paySize)) break;
            continue;
        }

        if (compBuf.size() < paySize) compBuf.resize(paySize);
        if (!stream.readExact(compBuf.data(), paySize)) break;

        const uint8_t* payloadPtr = compBuf.data();
        size_t payloadLen = paySize;
        if ((hdr.status & kStatusCompressed) != 0 && hdr.compression_code != 0) {
            size_t decompLen = 0;
            if (!decompressEvent(dctx, hdr.compression_code, compBuf.data(), paySize, decompBuf, decompLen)) {
                throw std::runtime_error("Decompression failed in " + rawPath + " eventID=" + std::to_string(eid));
            }
            payloadPtr = decompBuf.data();
            payloadLen = decompLen;
        }

        size_t offset = 0;
        for (uint8_t f = 0; f < hdr.fragment_count && offset + sizeof(RawFragmentHeader) <= payloadLen; ++f) {
            RawFragmentHeader fhdr{};
            std::memcpy(&fhdr, payloadPtr + offset, sizeof(fhdr));
            if (fhdr.marker != kFragmentMarker) {
                throw std::runtime_error("Bad EventFragment marker in " + rawPath + " eventID=" + std::to_string(eid));
            }
            const size_t fHdrSize = fhdr.header_size;
            const size_t fPaySize = fhdr.payload_size;
            if (offset + fHdrSize + fPaySize > payloadLen) break;

            if ((fhdr.source_id & kPMTSourceMask) == kPMTSourceId && (fhdr.source_id & 0x03u) == 0u) {
                processDigitizerPayload(payloadPtr + offset + fHdrSize, fPaySize, cp, *it, localMaxRawDiff);
                it->found = 1;
                ++matchedInFile;
                break;
            }
            offset += fHdrSize + fPaySize;
        }
    }
    return true;
}

bool peekFirstEventId(const std::string& rawPath, int64_t& firstEventIdOut) {
    int fd = ::open(rawPath.c_str(), O_RDONLY);
    RawEventHeader hdr{};
    bool ok = false;
    if (fd >= 0) {
        const ssize_t n = ::read(fd, &hdr, sizeof(hdr));
        ::close(fd);
        ok = (n == static_cast<ssize_t>(sizeof(hdr)) && hdr.marker == kEventMarker);
    }
    if (ok) {
        firstEventIdOut = static_cast<int64_t>(hdr.event_counter);
        return true;
    }
    return false;
}

std::vector<std::string> resolveRawFiles(const std::vector<std::string>& physFiles,
                                         const std::string& rawDir,
                                         int run) {
    char runBuf[16];
    std::snprintf(runBuf, sizeof(runBuf), "%06d", run);
    const std::string runStr(runBuf);

    const std::regex pat("Faser-Physics-" + runStr + R"(-(\d{5})(?:-(\d{5}))?-)");
    std::set<int> segIndices;
    for (const auto& pf : physFiles) {
        const std::string base = fs::path(pf).filename().string();
        std::smatch m;
        if (std::regex_search(base, m, pat)) {
            const int lo = std::stoi(m[1].str());
            const int hi = m[2].matched ? std::stoi(m[2].str()) : lo;
            for (int idx = lo; idx <= hi; ++idx) segIndices.insert(idx);
        }
    }
    if (!segIndices.empty()) {
        const int minIdx = *segIndices.begin();
        const int maxIdx = *segIndices.rbegin();
        if (minIdx > 0) segIndices.insert(minIdx - 1);
        segIndices.insert(maxIdx + 1);
    }

    std::vector<std::string> out;
    if (!segIndices.empty()) {
        for (int idx : segIndices) {
            char segBuf[16];
            std::snprintf(segBuf, sizeof(segBuf), "%05d", idx);
            const std::string cand = (fs::path(rawDir) / ("Faser-Physics-" + runStr + "-" + segBuf + ".raw")).string();
            if (fs::exists(cand) || rawDir.rfind("root://", 0) == 0) {
                out.push_back(cand);
            }
        }
        if (!out.empty()) return out;
    }

    // Fallback: list all physics raw files in rawDir
    if (fs::exists(rawDir) && fs::is_directory(rawDir)) {
        const std::string prefix = "Faser-Physics-" + runStr + "-";
        for (const auto& ent : fs::directory_iterator(rawDir)) {
            const std::string fn = ent.path().filename().string();
            if (fn.rfind(prefix, 0) == 0 && fn.size() > 4 && fn.substr(fn.size() - 4) == ".raw") {
                out.push_back(ent.path().string());
            }
        }
        std::sort(out.begin(), out.end());
    }
    return out;
}

void printUsage(const char* argv0) {
    std::cerr << "Usage: " << argv0
              << " --run <run_number> (--phys-files <f1,f2,...> | --phys-list <txt>)"
              << " (--raw-dir <dir> | --raw-files <r1,r2,...> | --raw-list <txt>) --output <out.root>"
              << " [--cond-db <ALLP200.db>] [--vv-diff <ns>] [--vt-diff <ns>] [--vp-diff <ns>]"
              << " [--disable-ps] [--disable-trig] [--filter-mode long_tracks|all_nt] [--max-missing-frac <f>] [--threads <n>]\n";
}

} // namespace

int main(int argc, char* argv[]) {
    ROOT::EnableThreadSafety();
    const auto wallStart = std::chrono::steady_clock::now();

    int run = -1;
    std::string physFilesArg;
    std::string physListArg;
    std::string rawDirArg;
    std::string rawFilesArg;
    std::string rawListArg;
    std::string outputPath;
    std::string condDbPath = "/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/sqlite200/ALLP200.db";
    double vvDiff = -1.0;
    double vtDiff = -1.0;
    double vpDiff = -1.0;
    bool disablePs = false;
    bool disableTrig = false;
    std::string filterMode = "long_tracks";
    double maxMissingFrac = 0.001;
    int threads = 4;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto needVal = [&](const std::string& f) -> std::string {
            if (i + 1 >= argc) throw std::runtime_error("Missing value for " + f);
            return argv[++i];
        };
        if (arg == "--run") run = std::stoi(needVal(arg));
        else if (arg == "--phys-files") physFilesArg = needVal(arg);
        else if (arg == "--phys-list") physListArg = needVal(arg);
        else if (arg == "--raw-dir") rawDirArg = needVal(arg);
        else if (arg == "--raw-files") rawFilesArg = needVal(arg);
        else if (arg == "--raw-list") rawListArg = needVal(arg);
        else if (arg == "--output" || arg == "-o") outputPath = needVal(arg);
        else if (arg == "--cond-db") condDbPath = needVal(arg);
        else if (arg == "--vv-diff") vvDiff = std::stod(needVal(arg));
        else if (arg == "--vt-diff") vtDiff = std::stod(needVal(arg));
        else if (arg == "--vp-diff") vpDiff = std::stod(needVal(arg));
        else if (arg == "--disable-ps") disablePs = true;
        else if (arg == "--disable-trig") disableTrig = true;
        else if (arg == "--filter-mode") filterMode = needVal(arg);
        else if (arg == "--max-missing-frac") maxMissingFrac = std::stod(needVal(arg));
        else if (arg == "--threads" || arg == "-j") threads = std::max(1, std::stoi(needVal(arg)));
        else {
            printUsage(argv[0]);
            return 1;
        }
    }

    if (run < 0 || outputPath.empty() ||
        (physFilesArg.empty() && physListArg.empty()) ||
        (rawDirArg.empty() && rawFilesArg.empty() && rawListArg.empty()) ||
        (filterMode != "long_tracks" && filterMode != "all_nt")) {
        printUsage(argv[0]);
        return 1;
    }

    if (vvDiff < 0.0) {
        if (15821 <= run && run <= 16924) vvDiff = 35.783;
        else if (run >= 18500) vvDiff = 33.166;
        else vvDiff = 33.165;
    }
    if (vtDiff < 0.0) {
        if (15821 <= run && run <= 16924) vtDiff = 34.872;
        else if (run >= 18500) vtDiff = 34.930;
        else vtDiff = 34.725;
    }
    if (vpDiff < 0.0) {
        if (15821 <= run && run <= 16924) vpDiff = 53.512;
        else if (run >= 18500) vpDiff = 13.330;
        else vpDiff = 53.625;
    }

    std::vector<std::string> physFiles;
    if (!physFilesArg.empty()) {
        auto v = splitComma(physFilesArg);
        physFiles.insert(physFiles.end(), v.begin(), v.end());
    }
    if (!physListArg.empty()) {
        auto v = readLines(physListArg);
        physFiles.insert(physFiles.end(), v.begin(), v.end());
    }
    if (physFiles.empty()) {
        std::cerr << "[ERROR] No PHYS input files given.\n";
        return 1;
    }

    const CondParams cp = queryConditions(condDbPath, run);
    std::cout << "[RC] run=" << run
              << " physFiles=" << physFiles.size()
              << " filter=" << filterMode
              << " disablePs=" << (disablePs ? 1 : 0)
              << " disableTrig=" << (disableTrig ? 1 : 0)
              << " diffs=(V2:" << vvDiff << ", PS:" << vpDiff << ", Trig:" << vtDiff << ")"
              << " cond=(nomTrig=" << cp.nomTrigNs << ", trigOff=" << cp.trigOffNs
              << ", range=" << cp.rangeV << ", baseLo=" << cp.baseLo << ")"
              << " threads=" << threads << std::endl;

    // Step 1: Read target events from PHYS nt files in parallel across worker threads
    const int nPhysThreads = std::min<int>(threads, static_cast<int>(physFiles.size()));
    std::vector<std::vector<TargetEvent>> perPhysTargets(physFiles.size());
    std::atomic<size_t> nextPhysIdx{0};
    std::atomic<int64_t> nNtTotal{0};
    std::atomic<int64_t> nFb1{0}, nFb2{0}, nFb3{0}, nFb0{0};
    std::mutex errMtx;
    std::string physErr;

    auto readPhysWorker = [&]() {
        while (true) {
            const size_t idx = nextPhysIdx.fetch_add(1);
            if (idx >= physFiles.size()) break;
            try {
                const std::string path = toXrdIfNeeded(physFiles[idx]);
                std::unique_ptr<TFile> f(TFile::Open(path.c_str(), "READ"));
                if (!f || f->IsZombie()) {
                    throw std::runtime_error("Cannot open PHYS file: " + path);
                }
                TTree* t = dynamic_cast<TTree*>(f->Get("nt"));
                if (!t) throw std::runtime_error("Missing 'nt' tree in " + path);

                t->SetBranchStatus("*", false);
                auto enableIfExists = [&](const char* bname, void* addr) {
                    if (t->GetBranch(bname)) {
                        t->SetBranchStatus(bname, true);
                        t->SetBranchAddress(bname, addr);
                        return true;
                    }
                    return false;
                };

                Int_t rVal = 0, evtId = 0, longTracks = 0;
                Float_t vnBl[2]{0.0f, 0.0f}, vnRaw[2]{0.0f, 0.0f};
                Int_t vnSt[2]{0, 0};
                Float_t v2Lt[2]{kNaNF, kNaNF};
                Int_t v2St[2]{-1, -1};
                Float_t psLt[2]{kNaNF, kNaNF};
                Int_t psSt[2]{-1, -1};
                Float_t trLt[4]{kNaNF, kNaNF, kNaNF, kNaNF};
                Int_t trSt[4]{-1, -1, -1, -1};

                const bool hasLongTracks = enableIfExists("longTracks", &longTracks);
                const bool hasRunBr = enableIfExists("run", &rVal);
                if (!enableIfExists("eventID", &evtId)) {
                    throw std::runtime_error("Missing eventID branch in " + path);
                }
                enableIfExists("VetoNu0_baseline", &vnBl[0]);
                enableIfExists("VetoNu1_baseline", &vnBl[1]);
                enableIfExists("VetoNu0_raw_charge", &vnRaw[0]);
                enableIfExists("VetoNu1_raw_charge", &vnRaw[1]);
                enableIfExists("VetoNu0_status", &vnSt[0]);
                enableIfExists("VetoNu1_status", &vnSt[1]);
                enableIfExists("Veto20_localtime", &v2Lt[0]);
                enableIfExists("Veto21_localtime", &v2Lt[1]);
                enableIfExists("Veto20_status", &v2St[0]);
                enableIfExists("Veto21_status", &v2St[1]);
                enableIfExists("Preshower0_localtime", &psLt[0]);
                enableIfExists("Preshower1_localtime", &psLt[1]);
                enableIfExists("Preshower0_status", &psSt[0]);
                enableIfExists("Preshower1_status", &psSt[1]);
                enableIfExists("Timing0_localtime", &trLt[0]);
                enableIfExists("Timing1_localtime", &trLt[1]);
                enableIfExists("Timing2_localtime", &trLt[2]);
                enableIfExists("Timing3_localtime", &trLt[3]);
                enableIfExists("Timing0_status", &trSt[0]);
                enableIfExists("Timing1_status", &trSt[1]);
                enableIfExists("Timing2_status", &trSt[2]);
                enableIfExists("Timing3_status", &trSt[3]);

                const Long64_t nEnt = t->GetEntries();
                nNtTotal.fetch_add(nEnt);
                std::vector<TargetEvent> local;
                local.reserve((filterMode == "all_nt") ? static_cast<size_t>(nEnt) : static_cast<size_t>(nEnt / 4 + 1));

                int64_t lfb1 = 0, lfb2 = 0, lfb3 = 0, lfb0 = 0;
                for (Long64_t i = 0; i < nEnt; ++i) {
                    t->GetEntry(i);
                    if (hasRunBr && rVal != run) continue;
                    if (filterMode == "long_tracks" && hasLongTracks && longTracks <= 0) continue;

                    TargetEvent ev;
                    ev.eventId = static_cast<int64_t>(evtId);
                    ev.baseline[0] = vnBl[0];
                    ev.baseline[1] = vnBl[1];
                    ev.ntRawCharge[0] = vnRaw[0];
                    ev.ntRawCharge[1] = vnRaw[1];
                    ev.vnStatus[0] = vnSt[0];
                    ev.vnStatus[1] = vnSt[1];

                    const float v2 = meanGoodTime(v2St, v2Lt);
                    if (std::isfinite(v2)) {
                        ev.expectedTime = v2 - static_cast<float>(vvDiff);
                        ev.fallbackMode = 1;
                        ++lfb1;
                    } else {
                        const float ps = disablePs ? kNaNF : meanGoodTime(psSt, psLt);
                        if (std::isfinite(ps)) {
                            ev.expectedTime = ps - static_cast<float>(vpDiff);
                            ev.fallbackMode = 2;
                            ++lfb2;
                        } else {
                            const float tr = disableTrig ? kNaNF : meanGoodTime(trSt, trLt);
                            if (std::isfinite(tr)) {
                                ev.expectedTime = tr - static_cast<float>(vtDiff);
                                ev.fallbackMode = 3;
                                ++lfb3;
                            } else {
                                ev.expectedTime = kNaNF;
                                ev.fallbackMode = 0;
                                ++lfb0;
                            }
                        }
                    }
                    local.push_back(ev);
                }
                nFb1.fetch_add(lfb1);
                nFb2.fetch_add(lfb2);
                nFb3.fetch_add(lfb3);
                nFb0.fetch_add(lfb0);
                perPhysTargets[idx] = std::move(local);
            } catch (const std::exception& e) {
                std::lock_guard<std::mutex> lk(errMtx);
                if (physErr.empty()) physErr = e.what();
            }
        }
    };

    {
        std::vector<std::thread> pool;
        for (int t = 0; t < nPhysThreads; ++t) pool.emplace_back(readPhysWorker);
        for (auto& th : pool) th.join();
    }
    if (!physErr.empty()) {
        std::cerr << "[ERROR] " << physErr << std::endl;
        return 2;
    }

    size_t totalTargets = 0;
    for (const auto& v : perPhysTargets) totalTargets += v.size();
    std::vector<TargetEvent> targets;
    targets.reserve(totalTargets);
    for (auto& v : perPhysTargets) {
        targets.insert(targets.end(), v.begin(), v.end());
        std::vector<TargetEvent>().swap(v);
    }
    std::sort(targets.begin(), targets.end(),
              [](const TargetEvent& a, const TargetEvent& b) { return a.eventId < b.eventId; });
    targets.erase(
        std::unique(targets.begin(), targets.end(),
                    [](const TargetEvent& a, const TargetEvent& b) { return a.eventId == b.eventId; }),
        targets.end());

    const auto physDone = std::chrono::steady_clock::now();
    std::cout << "[RC] PHYS loaded: n_nt=" << nNtTotal.load()
              << " n_target=" << targets.size()
              << " fb=(V2:" << nFb1.load() << ", PS:" << nFb2.load()
              << ", Trig:" << nFb3.load() << ", None:" << nFb0.load() << ")"
              << " dt=" << std::chrono::duration<double>(physDone - wallStart).count() << "s"
              << std::endl;

    if (!targets.empty()) {
        // Step 2: Resolve initial .raw files and stream in parallel
        std::vector<std::string> rawFiles;
        if (!rawFilesArg.empty()) {
            auto s = splitComma(rawFilesArg);
            rawFiles.insert(rawFiles.end(), s.begin(), s.end());
        }
        if (!rawListArg.empty()) {
            auto s = readLines(rawListArg);
            rawFiles.insert(rawFiles.end(), s.begin(), s.end());
        }
        if (rawFiles.empty() && !rawDirArg.empty()) {
            rawFiles = resolveRawFiles(physFiles, rawDirArg, run);
        }
        if (rawFiles.empty()) {
            std::cerr << "[ERROR] No .raw files resolved for run " << run << std::endl;
            return 3;
        }

        double maxRawDiff = 0.0;
        std::unordered_set<std::string> scannedRaw;

        auto runRawBatch = [&](const std::vector<std::string>& batch) {
            if (batch.empty()) return;
            for (const auto& p : batch) scannedRaw.insert(fs::path(p).filename().string());
            const int nWorkers = std::min<int>(threads, static_cast<int>(batch.size()));
            std::atomic<size_t> nextRawIdx{0};
            std::atomic<size_t> totalMatched{0};
            std::mutex resMtx;
            std::string rawErr;

            auto rawWorker = [&]() {
                ZSTD_DCtx* dctx = ZSTD_createDCtx();
                std::vector<uint8_t> compBuf(2 * 1024 * 1024);
                std::vector<uint8_t> decompBuf(8 * 1024 * 1024);
                BufferedStream stream(4 * 1024 * 1024);
                double localMaxDiff = 0.0;
                size_t localMatched = 0;

                while (true) {
                    const size_t i = nextRawIdx.fetch_add(1);
                    if (i >= batch.size()) break;
                    try {
                        size_t matchedInFile = 0;
                        if (!scanRawFile(batch[i], targets, cp, localMaxDiff, matchedInFile, dctx, compBuf, decompBuf, stream)) {
                            throw std::runtime_error("Cannot open raw file: " + batch[i]);
                        }
                        localMatched += matchedInFile;
                    } catch (const std::exception& e) {
                        std::lock_guard<std::mutex> lk(resMtx);
                        if (rawErr.empty()) rawErr = e.what();
                    }
                }
                if (dctx) ZSTD_freeDCtx(dctx);
                std::lock_guard<std::mutex> lk(resMtx);
                if (localMaxDiff > maxRawDiff) maxRawDiff = localMaxDiff;
                totalMatched.fetch_add(localMatched);
            };

            std::vector<std::thread> pool;
            for (int t = 0; t < nWorkers; ++t) pool.emplace_back(rawWorker);
            for (auto& th : pool) th.join();
            if (!rawErr.empty()) throw std::runtime_error(rawErr);
        };

        try {
            runRawBatch(rawFiles);
        } catch (const std::exception& e) {
            std::cerr << "[ERROR] " << e.what() << std::endl;
            return 4;
        }

        // Recovery pass if any target events fell into neighboring/unlisted .raw files
        std::vector<int64_t> missingIds;
        for (const auto& ev : targets) {
            if (!ev.found) missingIds.push_back(ev.eventId);
        }
        if (!missingIds.empty() && !rawDirArg.empty() && fs::exists(rawDirArg) && fs::is_directory(rawDirArg)) {
            char runBuf[16];
            std::snprintf(runBuf, sizeof(runBuf), "%06d", run);
            const std::string prefix = "Faser-Physics-" + std::string(runBuf) + "-";
            std::vector<std::pair<int64_t, std::string>> allDirFiles;
            for (const auto& ent : fs::directory_iterator(rawDirArg)) {
                const std::string fn = ent.path().filename().string();
                if (fn.rfind(prefix, 0) == 0 && fn.size() > 4 && fn.substr(fn.size() - 4) == ".raw") {
                    int64_t fid = -1;
                    if (peekFirstEventId(ent.path().string(), fid)) {
                        allDirFiles.emplace_back(fid, ent.path().string());
                    }
                }
            }
            std::sort(allDirFiles.begin(), allDirFiles.end());
            std::set<std::string> extraSet;
            for (int64_t mid : missingIds) {
                auto it = std::upper_bound(
                    allDirFiles.begin(), allDirFiles.end(), mid,
                    [](int64_t v, const std::pair<int64_t, std::string>& p) { return v < p.first; });
                if (it != allDirFiles.begin()) {
                    --it;
                    const std::string fn = fs::path(it->second).filename().string();
                    if (scannedRaw.count(fn) == 0) extraSet.insert(it->second);
                }
            }
            if (!extraSet.empty()) {
                std::cout << "[RC] Recovery pass for " << missingIds.size()
                          << " missing events across " << extraSet.size() << " additional .raw files." << std::endl;
                std::vector<std::string> extraBatch(extraSet.begin(), extraSet.end());
                runRawBatch(extraBatch);
            }
        }

        int64_t nFound = 0;
        for (const auto& ev : targets) {
            if (ev.found) ++nFound;
        }
        const int64_t nMissing = static_cast<int64_t>(targets.size()) - nFound;
        const double missFrac = targets.empty() ? 0.0 : (static_cast<double>(nMissing) / static_cast<double>(targets.size()));
        const auto rawDone = std::chrono::steady_clock::now();
        std::cout << "[RC] RAW done: n_found=" << nFound << "/" << targets.size()
                  << " missing=" << nMissing
                  << " max_abs_raw_diff=" << maxRawDiff << " pC"
                  << " dt=" << std::chrono::duration<double>(rawDone - physDone).count() << "s"
                  << std::endl;

        if (missFrac > maxMissingFrac && nMissing > 5) {
            std::cerr << "[ERROR] Too many missing raw events: " << nMissing
                      << " / " << targets.size() << " (" << (missFrac * 100.0) << "%)" << std::endl;
            return 5;
        }

        // Step 3: Write ZSTD-5 compressed ROOT output with exact 4 branches + rc_summary
        fs::path outP(outputPath);
        if (outP.has_parent_path()) fs::create_directories(outP.parent_path());
        std::unique_ptr<TFile> outFile(TFile::Open(outputPath.c_str(), "RECREATE", "", 505));
        if (!outFile || outFile->IsZombie()) {
            std::cerr << "[ERROR] Cannot create output ROOT file: " << outputPath << std::endl;
            return 6;
        }
        TTree* tree = new TTree("tree", "tree");
        Int_t outRun = run;
        Int_t outEvt = 0;
        Float_t outQ0 = kNaNF, outQ1 = kNaNF;
        tree->Branch("run", &outRun, "run/I");
        tree->Branch("event", &outEvt, "event/I");
        tree->Branch("myVetoNu0_rawCharge35", &outQ0, "myVetoNu0_rawCharge35/F");
        tree->Branch("myVetoNu1_rawCharge35", &outQ1, "myVetoNu1_rawCharge35/F");

        for (const auto& ev : targets) {
            outEvt = static_cast<Int_t>(ev.eventId);
            outQ0 = ev.q35[0];
            outQ1 = ev.q35[1];
            tree->Fill();
        }
        tree->Write();

        TTree* sumTree = new TTree("rc_summary", "rc_summary");
        Long64_t sNt = nNtTotal.load();
        Long64_t sTgt = static_cast<Long64_t>(targets.size());
        Long64_t sFnd = nFound;
        Long64_t sFb1 = nFb1.load(), sFb2 = nFb2.load(), sFb3 = nFb3.load(), sFb0 = nFb0.load();
        Double_t sMaxRawDiff = maxRawDiff;
        sumTree->Branch("run", &outRun, "run/I");
        sumTree->Branch("n_nt_total", &sNt, "n_nt_total/L");
        sumTree->Branch("n_target", &sTgt, "n_target/L");
        sumTree->Branch("n_found", &sFnd, "n_found/L");
        sumTree->Branch("n_fb1_veto2", &sFb1, "n_fb1_veto2/L");
        sumTree->Branch("n_fb2_ps", &sFb2, "n_fb2_ps/L");
        sumTree->Branch("n_fb3_trig", &sFb3, "n_fb3_trig/L");
        sumTree->Branch("n_fb0_none", &sFb0, "n_fb0_none/L");
        sumTree->Branch("max_abs_raw_diff", &sMaxRawDiff, "max_abs_raw_diff/D");
        sumTree->Fill();
        sumTree->Write();
        outFile->Close();
    } else {
        fs::path outP(outputPath);
        if (outP.has_parent_path()) fs::create_directories(outP.parent_path());
        std::unique_ptr<TFile> outFile(TFile::Open(outputPath.c_str(), "RECREATE", "", 505));
        if (!outFile || outFile->IsZombie()) {
            std::cerr << "[ERROR] Cannot create output ROOT file: " << outputPath << std::endl;
            return 6;
        }
        TTree* tree = new TTree("tree", "tree");
        Int_t outRun = run, outEvt = 0;
        Float_t outQ0 = kNaNF, outQ1 = kNaNF;
        tree->Branch("run", &outRun, "run/I");
        tree->Branch("event", &outEvt, "event/I");
        tree->Branch("myVetoNu0_rawCharge35", &outQ0, "myVetoNu0_rawCharge35/F");
        tree->Branch("myVetoNu1_rawCharge35", &outQ1, "myVetoNu1_rawCharge35/F");
        tree->Write();

        TTree* sumTree = new TTree("rc_summary", "rc_summary");
        Long64_t sNt = nNtTotal.load(), sTgt = 0, sFnd = 0, sFb1 = 0, sFb2 = 0, sFb3 = 0, sFb0 = 0;
        Double_t sMaxRawDiff = 0.0;
        sumTree->Branch("run", &outRun, "run/I");
        sumTree->Branch("n_nt_total", &sNt, "n_nt_total/L");
        sumTree->Branch("n_target", &sTgt, "n_target/L");
        sumTree->Branch("n_found", &sFnd, "n_found/L");
        sumTree->Branch("n_fb1_veto2", &sFb1, "n_fb1_veto2/L");
        sumTree->Branch("n_fb2_ps", &sFb2, "n_fb2_ps/L");
        sumTree->Branch("n_fb3_trig", &sFb3, "n_fb3_trig/L");
        sumTree->Branch("n_fb0_none", &sFb0, "n_fb0_none/L");
        sumTree->Branch("max_abs_raw_diff", &sMaxRawDiff, "max_abs_raw_diff/D");
        sumTree->Fill();
        sumTree->Write();
        outFile->Close();
    }

    const auto wallEnd = std::chrono::steady_clock::now();
    std::cout << "[RC] Total wall time: "
              << std::chrono::duration<double>(wallEnd - wallStart).count() << "s" << std::endl;
    return 0;
}
