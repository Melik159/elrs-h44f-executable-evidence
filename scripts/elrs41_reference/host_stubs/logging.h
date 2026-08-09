#pragma once

#include <cstddef>
#include <cstring>

#define DBGLN(...) do { } while (0)

extern const char version[];

inline std::size_t strlcpy(char *destination, const char *source, std::size_t size) {
    const std::size_t source_len = std::strlen(source);
    if (size != 0U) {
        const std::size_t copy_len = source_len < size - 1U ? source_len : size - 1U;
        std::memcpy(destination, source, copy_len);
        destination[copy_len] = '\0';
    }
    return source_len;
}

inline std::size_t strlcat(char *destination, const char *source, std::size_t size) {
    const std::size_t destination_len = ::strnlen(destination, size);
    if (destination_len == size) {
        return size + std::strlen(source);
    }
    return destination_len + strlcpy(
        destination + destination_len, source, size - destination_len
    );
}
