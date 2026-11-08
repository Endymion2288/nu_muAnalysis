// Decode source-version identifiers without initializing a current FaserID helper
// against an incompatible legacy dictionary. No guessed bit shifts/permutations.
#include "IdDictParser/IdDictParser.h"
#include "Identifier/Identifier.h"
#include "Identifier/Identifier32.h"
#include "Identifier/ExpandedIdentifier.h"
#include <memory>
#include <vector>
#include <stdexcept>
#include <sstream>

class Stage185Identity {
    IdDictParser parser;
    IdDictDictionary* dictionary;
public:
    Stage185Identity(const std::string& file) {
        auto& manager=parser.parse(file);
        dictionary=manager.find_dictionary("Scintillator");
        if(!dictionary)throw std::runtime_error("Missing historical dictionary");
    }
    std::vector<unsigned int> decode(unsigned int id32) const {
        const Identifier id{Identifier32(id32)};
        std::vector<std::vector<unsigned int>> candidates;
        // The generic prefix overload does not consume prefix bits and skips
        // zero-width fields. Decode explicit fields in actual dictionary regions,
        // including fixed station/PMT fields, then require an exact roundtrip.
        for(size_t region=0;region<dictionary->m_regions.size();++region) {
            const auto* schema=dictionary->m_regions[region];
            if(schema->m_is_empty || schema->m_implementation.size()!=5)continue;
            ExpandedIdentifier expanded;
            std::vector<unsigned int> values;
            bool valid=true;
            for(size_t field=0;field<5;++field) {
                int value=0;
                if(dictionary->unpack(id,0,field,region,value)!=0 ||
                   !schema->m_implementation[field].field().match(value)) {valid=false;break;}
                expanded<<value;values.push_back(value);
            }
            if(!valid)continue;
            Identifier packed;
            if(dictionary->pack32(expanded,0,4,packed)==0 && packed==id)candidates.push_back(values);
        }
        if(candidates.size()!=1)throw std::runtime_error("Historical ID has no unique region and exact roundtrip");
        return candidates[0];
    }
};
