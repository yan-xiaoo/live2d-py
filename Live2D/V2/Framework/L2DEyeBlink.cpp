#include "L2DEyeBlink.hpp"
#include "../Model/ALive2DModel.hpp"
#include "../Model/ModelContext.hpp"
#include "../Core/Id.hpp"
#include "../Util/UtSystem.hpp"
#include <cstdlib>
namespace live2d {
L2DEyeBlink::L2DEyeBlink() {}
void L2DEyeBlink::setEyeMotion(int closeMs, int closedMs, int openMs) {
    mClosingMs = static_cast<float>(closeMs);
    mClosedMs = static_cast<float>(closedMs);
    mOpeningMs = static_cast<float>(openMs);
}
void L2DEyeBlink::updateParam(ALive2DModel* model) {
    double now = UtSystem::getUserTimeMSec();
    mCurrentTime = now;

    switch (mState) {
    case FIRST:
        mNextBlinkTime = now + static_cast<double>(rand() % (2 * (int)mBlinkIntervalMs));
        mState = INTERVAL;
        break;
    case INTERVAL:
        if (now >= mNextBlinkTime) {
            mState = CLOSING;
            mStateStartTime = now;
        }
        break;
    case CLOSING: {
        double elapsed = now - mStateStartTime;
        float v = static_cast<float>(1.0 - (elapsed / mClosingMs));
        if (v <= 0) { v = 0; mState = CLOSED; mStateStartTime = now; }
        model->setParamFloat(model->getModelContext()->getParamIndex(&Id::getID(mEyeLId)), v);
        model->setParamFloat(model->getModelContext()->getParamIndex(&Id::getID(mEyeRId)), v);
        break;
    }
    case CLOSED: {
        model->setParamFloat(model->getModelContext()->getParamIndex(&Id::getID(mEyeLId)), 0);
        model->setParamFloat(model->getModelContext()->getParamIndex(&Id::getID(mEyeRId)), 0);
        double elapsed = now - mStateStartTime;
        if (elapsed >= mClosedMs) { mState = OPENING; mStateStartTime = now; }
        break;
    }
    case OPENING: {
        double elapsed = now - mStateStartTime;
        float v = static_cast<float>(elapsed / mOpeningMs);
        if (v >= 1.0f) { v = 1.0f; mState = INTERVAL;
            mNextBlinkTime = now + mBlinkIntervalMs + static_cast<double>(rand() % (int)mBlinkIntervalMs); }
        model->setParamFloat(model->getModelContext()->getParamIndex(&Id::getID(mEyeLId)), v);
        model->setParamFloat(model->getModelContext()->getParamIndex(&Id::getID(mEyeRId)), v);
        break;
    }
    }
}
} // namespace live2d
