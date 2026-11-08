// Official framing and trigger/digitizer decoding; no fitted-charge dependence.
#include "EventFormats/DAQFormats.hpp"
#include "EventFormats/DigitizerDataFragment.hpp"
#include "EventFormats/TLBDataFragment.hpp"
#include <array>
#include <iostream>
#include <string>
#include <sstream>

int main(int argc, char** argv) {
    if (argc != 3) return 2;
    std::ifstream input(argv[1], std::ios::binary);
    if (!input) return 3;
    const int limit = std::stoi(argv[2]);
    int raw = 0, physics = 0, strictCount = 0;
    while (input.good() && input.peek() != EOF && physics < limit && raw < 16384
           && input.tellg() < 134217728) {
        DAQFormats::EventFull event(input);
        const int rawEntry = raw++;
        if (event.event_tag() != DAQFormats::PhysicsTag) continue;
        if (event.run_number() != 15838) return 4;
        std::ostringstream tlbs;
        int tlbN = 0, validN = 0, tap = -1, tbp = -1;
        for (const auto& id : event.getFragmentIDs()) {
            const auto* fragment = event.find_fragment(id);
            if ((fragment->source_id() & 0xffff0000) != DAQFormats::TriggerSourceID) continue;
            if (tlbN++) tlbs << ',';
            const auto size = fragment->payload_size();
            const auto* data = fragment->payload<const uint32_t*>();
            const auto header = size >= 4 ? data[0] : 0;
            const bool known = header == TLBDataFormat::TRIGGER_HEADER_V1
                || header == TLBDataFormat::TRIGGER_HEADER_V2 || header == TLBDataFormat::TRIGGER_HEADER_V3;
            // Official decoder reads its checksum before checking size: preflight exact framing.
            const auto expected = sizeof(TLBDataFormat::TLBEventV1)
                + (header == TLBDataFormat::TRIGGER_HEADER_V1 ? 0 : sizeof(uint32_t));
            tlbs << "{\"source_id\":" << fragment->source_id() << ",\"bytes\":" << size
                 << ",\"header\":" << header << ",\"supported\":" << known
                 << ",\"framed\":" << (known && size == expected);
            if (known && size == expected) {
                TLBDataFormat::TLBDataFragment tlb(data, size);
                const bool valid = tlb.valid();
                tlbs << ",\"valid\":" << valid << ",\"version\":" << int(tlb.version())
                     << ",\"checksum_applicable\":" << (tlb.version() >= 2)
                     << ",\"checksum_error\":" << tlb.has_checksum_error()
                     << ",\"frameid_error\":" << tlb.has_frameid_error();
                if (valid) {
                    ++validN;tap = tlb.tap();tbp = tlb.tbp();
                    tlbs << ",\"TAP\":" << tap << ",\"TBP\":" << tbp
                         << ",\"input_bits\":" << int(tlb.input_bits())
                         << ",\"input_bits_next\":" << int(tlb.input_bits_next_clk())
                         << ",\"event_id\":" << tlb.event_id() << ",\"bc_id\":" << tlb.bc_id()
                         << ",\"orbit_id\":" << tlb.orbit_id();
                }
            }
            tlbs << '}';
        }
        const bool strict = tlbN == 1 && validN == 1 && tap == 16 && tbp == 16;
        const bool keep = physics < 56 || (strict && strictCount < 256);
        if (strict) ++strictCount;
        std::cout << "{\"run\":" << event.run_number() << ",\"eventID\":" << event.event_id()
                  << ",\"counter\":" << event.event_counter() << ",\"timestamp_us\":" << event.timestamp()
                  << ",\"status\":" << event.status() << ",\"trigger_bits\":" << event.trigger_bits()
                  << ",\"raw_entry\":" << rawEntry << ",\"physics_entry\":" << physics
                  << ",\"bytes_through\":" << input.tellg() << ",\"strict\":" << strict
                  << ",\"retained\":" << keep << ",\"tlb\":[" << tlbs.str() << "],\"boards\":[";
        int boardN = 0;
        for (const auto& id : event.getFragmentIDs()) {
            const auto* fragment = event.find_fragment(id);
            if ((fragment->source_id() & 0xffff0000) != DAQFormats::PMTSourceID) continue;
            if (boardN++) std::cout << ',';
            std::cout << "{\"source_id\":" << fragment->source_id() << ",\"board\":" << (fragment->source_id() & 3)
                      << ",\"bytes\":" << fragment->payload_size();
            if (keep) {
                try {
                    DigitizerDataFragment digi(fragment->payload<const uint32_t*>(),fragment->payload_size());
                    std::cout << ",\"decoded\":1,\"valid\":" << digi.valid()
                              << ",\"board_fail\":" << digi.board_fail_flag()
                              << ",\"tag\":" << digi.trigger_time_tag() << ",\"channels\":[";
                    bool first = true;
                    for (int c=0;c<16;++c) {
                        if (!digi.channel_has_data(c)) continue;
                        if (!first) std::cout << ',';first=false;
                        const auto& adc=digi.channel_adc_counts(c);
                        std::cout << "{\"channel\":" << c << ",\"adc\":[";
                        for (size_t j=0;j<adc.size();++j) {if (j) std::cout << ',';std::cout << adc[j];}
                        std::cout << "]}";
                    }
                    std::cout << ']';
                } catch (const std::exception&) {std::cout << ",\"decoded\":0";}
            }
            std::cout << '}';
        }
        std::cout << "]}\n";
        ++physics;
    }
    std::cerr << "raw_frames=" << raw << " physics=" << physics << " strict=" << strictCount
              << " bytes_through=" << input.tellg() << '\n';
    return physics == limit ? 0 : 5;
}
