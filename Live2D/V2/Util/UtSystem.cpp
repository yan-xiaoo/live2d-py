#include "UtSystem.hpp"
#include <chrono>

namespace live2d {

double UtSystem::getUserTimeMSec() {
    static const auto start = std::chrono::steady_clock::now();
    auto now = std::chrono::steady_clock::now();
    return std::chrono::duration<double, std::milli>(
               now - start).count();
}

} // namespace live2d
