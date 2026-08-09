// Offline audit wrapper. It links pinned upstream FHSS.cpp and random.cpp
// verbatim; no RF driver or device code is linked.
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <stdexcept>

#include "FHSS.h"
#include "options.h"

FirmwareOptionsStub firmwareOptions{1}; // FCC915 is domains[1] upstream
extern const char version[] = "offline-audit";

namespace {
std::uint32_t parse_u32(const char *text) {
    char *end = nullptr;
    const unsigned long value = std::strtoul(text, &end, 0);
    if (end == text || *end != '\0' || value > 0xFFFFFFFFUL) {
        throw std::invalid_argument("invalid unsigned 32-bit value");
    }
    return static_cast<std::uint32_t>(value);
}

std::uint32_t ota_uid_seed(
    std::uint8_t uid2_low7,
    std::uint8_t uid3,
    std::uint8_t uid4,
    std::uint8_t uid5,
    std::uint8_t ota_version) {
    return (static_cast<std::uint32_t>(uid2_low7) << 24U)
         + (static_cast<std::uint32_t>(uid3) << 16U)
         + (static_cast<std::uint32_t>(uid4) << 8U)
         + static_cast<std::uint32_t>(uid5 ^ ota_version);
}
}

int main(int argc, char **argv) {
    try {
        if (argc != 4) {
            std::cerr << "usage: direct_fhss_driver UID4 UID5 OUTPUT\\n";
            return 2;
        }
        const auto uid4 = static_cast<std::uint8_t>(parse_u32(argv[1]));
        const auto uid5 = static_cast<std::uint8_t>(parse_u32(argv[2]));
        std::ofstream output(argv[3], std::ios::binary | std::ios::trunc);
        if (!output) {
            throw std::runtime_error("cannot open output");
        }

        for (std::uint32_t candidate = 0; candidate < 32768U; ++candidate) {
            const auto uid2 = static_cast<std::uint8_t>((candidate >> 8U) & 0x7FU);
            const auto uid3 = static_cast<std::uint8_t>(candidate & 0xFFU);
            FHSSrandomiseFHSSsequence(ota_uid_seed(uid2, uid3, uid4, uid5, 4U));
            output.write(reinterpret_cast<const char *>(FHSSsequence), 240);
        }
        if (!output) {
            throw std::runtime_error("matrix write failed");
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
