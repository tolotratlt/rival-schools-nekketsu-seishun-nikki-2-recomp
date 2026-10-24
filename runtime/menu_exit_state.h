#pragma once

#include <cstdint>

namespace nsn2 {

struct ExitMenuResult {
    bool consume = false;
    bool quit = false;
};

// MODESEL uses internal mode ids, rather than the order of the visible list.
class ExitMenuState {
public:
    static constexpr unsigned youth_diary = 6;
    static constexpr unsigned options = 3;
    static constexpr uint16_t up = 0x0010;
    static constexpr uint16_t down = 0x0040;
    static constexpr uint16_t circle = 0x2000;
    static constexpr uint16_t cross = 0x4000;

    ExitMenuResult update(bool active, unsigned mode, uint16_t pressed) {
        const uint16_t edge = pressed & ~previous_;
        previous_ = pressed;
        if (!active) {
            selected_ = false;
            drain_ = false;
            return {};
        }
        // A consumed press must stay consumed until release. Otherwise its
        // remaining held frames become a new press in the original menu.
        if (drain_) {
            if (!pressed) drain_ = false;
            return {true, false};
        }
        if (!selected_) {
            if ((mode == options && (edge & down)) ||
                (mode == youth_diary && (edge & up))) {
                anchor_ = mode;
                selected_ = true;
                return {true, false};
            }
            return {};
        }
        if (edge & circle) return {true, true};
        if (edge & cross) {
            selected_ = false;
            drain_ = true;
            return {true, false};
        }
        if (edge & up) {
            selected_ = false;
            drain_ = anchor_ == options;
            return {drain_, false};
        }
        if (edge & down) {
            selected_ = false;
            drain_ = anchor_ == youth_diary;
            return {drain_, false};
        }
        return {true, false};
    }

    bool selected() const { return selected_; }
    unsigned anchor() const { return anchor_; }

private:
    uint16_t previous_ = 0;
    unsigned anchor_ = options;
    bool selected_ = false;
    bool drain_ = false;
};

} // namespace nsn2
