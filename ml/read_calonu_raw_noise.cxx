// Thin RAW reader: retain the official EventFormats framing and ADC decoder.
#include "EventFormats/DAQFormats.hpp"
#include "EventFormats/DigitizerDataFragment.hpp"
#include <array>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 4) return 2; // input, physics-event limit, run (cable IOV)
    std::ifstream input(argv[1], std::ios::binary);
    if (!input) return 3;
    const int limit = std::stoi(argv[2]);
    const int run = std::stoi(argv[3]);
    const std::array<int, 4> channels = run == 15838
        ? std::array<int, 4>{20, 21, 22, 23} : std::array<int, 4>{6, 7, 14, 15};
    int kept = 0, read = 0;
    while (input.good() && input.peek() != EOF && kept < limit) {
        DAQFormats::EventFull event(input);
        ++read;
        if (event.event_tag() != DAQFormats::PhysicsTag) continue;
        if (event.run_number() != static_cast<unsigned>(run)) return 4;
        std::array<std::vector<uint16_t>, 4> adc;
        std::array<int, 2> valid{-1, -1}, tag{-1, -1};
        for (const auto& id : event.getFragmentIDs()) {
            const auto* fragment = event.find_fragment(id);
            if ((fragment->source_id() & 0xffff0000) != DAQFormats::PMTSourceID) continue;
            const int board = fragment->source_id() & 3;
            if (board > 1) continue;
            DigitizerDataFragment digitizer(fragment->payload<const uint32_t*>(), fragment->payload_size());
            valid[board] = digitizer.valid() && !digitizer.board_fail_flag();
            tag[board] = digitizer.trigger_time_tag();
            for (int i = 0; i < 4; ++i) {
                if (channels[i] / 16 != board || !digitizer.channel_has_data(channels[i] % 16)) continue;
                adc[i] = digitizer.channel_adc_counts(channels[i] % 16);
            }
        }
        std::cout << "{\"run\":" << event.run_number() << ",\"eventID\":" << event.event_id()
                  << ",\"counter\":" << event.event_counter() << ",\"timestamp_us\":" << event.timestamp()
                  << ",\"status\":" << event.status() << ",\"trigger_bits\":" << event.trigger_bits()
                  << ",\"raw_entry\":" << read-1 << ",\"bytes_through\":" << input.tellg()
                  << ",\"board_valid\":[" << valid[0] << ',' << valid[1]
                  << "],\"board_time_tag\":[" << tag[0] << ',' << tag[1] << "],\"adc\":[";
        for (int i = 0; i < 4; ++i) {
            if (i) std::cout << ',';
            std::cout << '[';
            for (size_t j = 0; j < adc[i].size(); ++j) {
                if (j) std::cout << ',';
                std::cout << adc[i][j];
            }
            std::cout << ']';
        }
        std::cout << "]}" << std::endl;
        ++kept;
    }
    return kept == limit ? 0 : 5;
}
