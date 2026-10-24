#include "menu_exit_state.h"
#include <cassert>

using nsn2::ExitMenuState;

int main() {
    ExitMenuState state;
    using S = ExitMenuState;
    // Ordinary entries, including confirm, remain guest-owned.
    assert(!state.update(true, 0, S::down).consume);
    state.update(true, 0, 0);
    assert(!state.update(true, S::options, S::circle).quit);
    state.update(true, S::options, 0);
    // Down from Options selects Exit; a held button does not skip it.
    assert(state.update(true, S::options, S::down).consume);
    assert(state.selected());
    assert(state.update(true, S::options, S::down).consume);
    assert(state.selected());
    state.update(true, S::options, 0);
    assert(state.update(true, S::options, S::circle).quit);
    // Cancel returns to the same anchor and consumes the cancel press.
    state.update(true, S::options, 0);
    assert(state.update(true, S::options, S::cross).consume);
    assert(!state.selected());
    assert(state.update(true, S::options, S::cross).consume);
    state.update(true, S::options, 0);
    state.update(true, S::options, S::down);
    state.update(true, S::options, 0);
    assert(state.update(true, S::options, S::up).consume);
    assert(!state.selected());
    assert(state.update(true, S::options, S::up).consume);
    state.update(true, S::options, 0);
    state.update(true, S::options, S::down);
    state.update(true, S::options, 0);
    // Pass Down through to the guest's existing Options -> Youth Diary wrap.
    assert(!state.update(true, S::options, S::down).consume);
    assert(!state.selected());
    state.update(true, S::youth_diary, 0);
    assert(state.update(true, S::youth_diary, S::up).consume);
    state.update(true, S::youth_diary, 0);
    assert(state.update(true, S::youth_diary, S::down).consume);
    assert(state.update(true, S::youth_diary, S::down).consume);
    state.update(true, S::youth_diary, 0);
    state.update(true, S::youth_diary, S::up);
    state.update(true, S::youth_diary, 0);
    assert(!state.update(true, S::youth_diary, S::up).consume);
    // Leaving MODE SELECT cancels selection and never turns confirm into quit.
    state.update(true, S::options, 0);
    state.update(true, S::options, S::down);
    assert(!state.update(false, S::options, S::circle).quit);
    assert(!state.selected());
    // A button held while entering the scene does not act as a fresh press.
    state.update(false, S::options, S::down);
    assert(!state.update(true, S::options, S::down).consume);
}
