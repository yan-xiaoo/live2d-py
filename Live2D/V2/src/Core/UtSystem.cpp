#include "UtSystem.hpp"
#include <chrono>

namespace Live2D {
namespace V2 {

double UtSystem::getUserTimeMSec() {
    static const auto start = std::chrono::steady_clock::now();
    return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
}

}   // namespace V2
}   // namespace Live2D