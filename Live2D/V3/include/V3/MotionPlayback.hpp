#pragma once

#include <MotionPlaybackState.hpp>
#include <functional>
#include <memory>
#include <string>
#include <utility>

#include <Motion/CubismMotion.hpp>
#include <Motion/CubismMotionQueueEntry.hpp>

namespace Live2D {
namespace V3 {

// Each playback has its own queue-owned motion facade. Parsed curves remain
// cached, but Python callbacks are never stored on the shared CubismMotion.
class PlaybackMotion final : public Csm::ACubismMotion
{
public:
    PlaybackMotion(Csm::CubismMotion* motion, bool ownsMotion,
                   std::shared_ptr<MotionPlayback> playback)
        : _motion(motion), _ownsMotion(ownsMotion), _playback(std::move(playback))
    {
        SetFadeInTime(motion->GetFadeInTime());
        SetFadeOutTime(motion->GetFadeOutTime());
        SetWeight(motion->GetWeight());
        SetLoop(motion->GetLoop());
        SetLoopFadeIn(motion->GetLoopFadeIn());
    }

    ~PlaybackMotion() override
    {
        _playback->retired = true;
        if (_ownsMotion)
            Csm::ACubismMotion::Delete(_motion);
    }

    Csm::csmFloat32 GetDuration() override { return _motion->GetDuration(); }
    Csm::csmFloat32 GetLoopDuration() override { return _motion->GetLoopDuration(); }

    const Csm::csmVector<const Csm::csmString*>& GetFiredEvent(
        Csm::csmFloat32 before, Csm::csmFloat32 now) override
    {
        return _motion->GetFiredEvent(before, now);
    }

    void DoUpdateParameters(Csm::CubismModel* model, Csm::csmFloat32 time,
                            Csm::csmFloat32 weight,
                            Csm::CubismMotionQueueEntry* entry) override
    {
        _playback->started = true;
        _motion->DoUpdateParameters(model, time, weight, entry);
        // CubismMotion marks natural completion here. Early fade-out is handled
        // later by ACubismMotion, and cancellation must not report completion.
        if (entry->IsFinished())
            _playback->finished = true;
    }

private:
    Csm::CubismMotion* _motion;
    bool _ownsMotion;
    std::shared_ptr<MotionPlayback> _playback;
};

} // namespace V3
} // namespace Live2D
