#include "stage161_native.hxx"
#include "IdDictDetDescr/IdDictManager.h"
namespace Stage162 {
std::vector<std::string> dictionary(const IdDictManager& mgr) {
    const auto* dictionary=mgr.manager()->find_dictionary("Scintillator");
    if(!dictionary)throw std::runtime_error("No actual scint dictionary");
    return {dictionary->file_name(),dictionary->dict_tag(),std::to_string(dictionary->m_regions.size())};
}
}
