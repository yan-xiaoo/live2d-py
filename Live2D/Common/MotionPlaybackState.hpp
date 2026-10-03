#pragma once
#include <IModel.hpp>
#include <memory>
#include <string>

namespace Live2D {
// Retained by Model until queue traversal ends, so Python finalizers cannot
// re-enter a partially modified motion queue.
struct MotionPlayback {
    std::string group;
    int index;
    IModel::MotionCallback onStart;
    IModel::MotionCallback onFinish;
    bool started = false;
    bool finished = false;
    bool retired = false;
    bool cancelled = false;
};
}
