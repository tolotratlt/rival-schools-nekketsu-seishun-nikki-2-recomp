// Host-owned MODE SELECT extension. No disc or generated-code edits.
#include "menu_exit_state.h"
#include "gpu.h"
#include "mod_plugins.h"
#include "psx_sdl.h"
#include "sio.h"

#include <cstdio>
#include <cstdlib>

extern "C" void mod_register_frame_hook(void (*hook)(void));

namespace {
nsn2::ExitMenuState menu;
bool quit_queued = false;

// Stock MODESEL.BIN callbacks at file offsets 0, 4, 8; menu id persistence
// at 0x801f6330 is written by MODESEL's input handler at 0x800a41d0.
bool mode_select_active() {
    return psx_mod_read_word(0x800a2000) == 0x800a3f84 &&
        psx_mod_read_word(0x800a2004) == 0x800a4974 &&
        psx_mod_read_word(0x800a2008) == 0x800a5730 &&
        psx_mod_read_byte(0x801c8000) == 1;
}

uint32_t xy(unsigned x, unsigned y) { return (y << 16) | x; }

// Everything below is drawn with ordinary GPU commands (rectangles, sprites,
// VRAM-to-VRAM copies), never CPU reads or CPU-to-VRAM transfers: a VRAM read
// makes the hardware renderers sync the GPU image down, which froze MODE
// SELECT under Vulkan. Drawing to the display area is allowed while the
// extension draws (GP0 E1 bit 10), so raster commands write both 480i fields;
// end_draw() restores the game's drawing state.
constexpr uint32_t draw_to_display = 1u << 10;
uint32_t saved_status;
GpuDrawArea saved_area;

uint32_t texpage_bits(uint32_t status) {
    // GPUSTAT bits 0-10 match GP0 E1 bits 0-10; GPUSTAT 15 is E1 bit 11.
    return (status & 0x7ff) | ((status >> 4) & 0x800);
}

void begin_draw(unsigned x, unsigned y) {
    saved_status = gpu_read_gpustat();
    gpu_get_draw_area(&saved_area);
    gpu_write_gp0(0xe1000000 | texpage_bits(saved_status) | draw_to_display);
    gpu_write_gp0(0xe3000000 | (y << 10) | x);
    gpu_write_gp0(0xe4000000 | ((y + 479) << 10) | (x + 511));
    gpu_write_gp0(0xe5000000);
    gpu_write_gp0(0xe6000000);
}

void end_draw() {
    gpu_write_gp0(0xe1000000 | texpage_bits(saved_status));
    gpu_write_gp0(0xe3000000 | (saved_area.top << 10) | saved_area.left);
    gpu_write_gp0(0xe4000000 | (saved_area.bottom << 10) | saved_area.right);
    gpu_write_gp0(0xe5000000 | ((uint32_t(saved_area.offset_y) & 0x7ff) << 11) |
                  (uint32_t(saved_area.offset_x) & 0x7ff));
    gpu_write_gp0(0xe6000000 | ((saved_status >> 11) & 3));
}

// Hide text by copying one clean row of the panel over every row of the box.
void restore_panel(unsigned x, unsigned y, unsigned w, unsigned h, unsigned sample_y) {
    for (unsigned row = 0; row < h; ++row) {
        gpu_write_gp0(0x80000000);
        gpu_write_gp0(xy(x, sample_y));
        gpu_write_gp0(xy(x, y + row));
        gpu_write_gp0(xy(w, 1));
    }
}

// Stock menu art from the 4-bpp atlas already in VRAM (texel sx, sy from
// x 512, y 256), drawn as a sprite with its CLUT. No art is embedded in the
// executable: the frame and translated labels come from disc.
void menu_texture(unsigned sx, unsigned sy, unsigned x, unsigned y,
                  unsigned w, unsigned h, unsigned clut) {
    const unsigned page = 8 + sx / 256;   // 64-halfword pages from x 512; y 256 page
    gpu_write_gp0(0xe1000000 | (texpage_bits(saved_status) & ~0x1ffu) | page | 0x10 |
                  draw_to_display);
    gpu_write_gp0(0x65000000);   // opaque textured rectangle, raw texture
    gpu_write_gp0(xy(x, y));
    gpu_write_gp0((clut << 16) | (sy << 8) | (sx % 256));
    gpu_write_gp0(xy(w, h));
}

void rectangle(unsigned x, unsigned y, unsigned w, unsigned h, uint32_t color) {
    gpu_write_gp0(0x60000000 | (color & 0xffffff));   // opaque flat rectangle
    gpu_write_gp0(xy(x, y));
    gpu_write_gp0(xy(w, h));
}

// New UI lettering, drawn at its final pixel size. Rows are five-bit masks.
const uint8_t* glyph(char c) {
    static const uint8_t letters[][7] = {
        {31,16,16,30,16,16,31}, // E
        {17,17,10,4,10,17,17}, // X
        {31,4,4,4,4,4,31}, // I
        {31,4,4,4,4,4,4}, // T
        {14,17,17,17,21,18,13}, // Q
        {17,17,17,17,17,17,14}, // U
        {14,17,16,23,17,17,15}, // G
        {14,17,17,31,17,17,17}, // A
        {17,27,21,21,17,17,17}, // M
    };
    const char* chars = "EXITQUGAM";
    for (unsigned i = 0; chars[i]; ++i) if (chars[i] == c) return letters[i];
    return nullptr;
}

void text(unsigned x, unsigned y, const char* value, unsigned scale, uint32_t color) {
    for (; *value; ++value, x += 6 * scale) {
        const uint8_t* rows = glyph(*value);
        if (!rows) continue;
        for (unsigned row = 0; row < 7; ++row)
            for (unsigned col = 0; col < 5; ++col)
                if (rows[row] & (16 >> col))
                    rectangle(x + col * scale, y + row * scale, scale, scale, color);
    }
}

void draw_exit() {
    GpuDisplayInfo display{};
    gpu_get_display_info(&display);
    if (display.disabled || display.depth24 || display.width != 512 || display.height != 480)
        return;
    const unsigned x = display.display_x, y = display.display_y;
    if (x + 512 > 1024 || y + 480 > 512) return;
    begin_draw(x, y);
    // There is one unused row below Options, inside the original green panel.
    const bool selected = menu.selected();
    restore_panel(x + 40, y + 426, 104, 24, y + 134);
    if (selected) {
        const bool youth = menu.anchor() == nsn2::ExitMenuState::youth_diary;
        // The opaque bounds of the stock 160x48 selector are 142x43.
        restore_panel(x + 12, y + (youth ? 72 : 384), 142, 43, y + 134);
        if (!youth)
            menu_texture(1024, 96, x + 40, y + 376, 96, 24, 0x7881);
        menu_texture(youth ? 888 : 1024, youth ? 64 : 120,
                     x + 40, y + (youth ? 88 : 400), youth ? 104 : 96, 24, 0x7881);
        menu_texture(304, 0, x + 12, y + 420, 160, 48, 0x78c2);
    }
    text(x + 66, y + 433, "EXIT", 2, 0xf8f8f8);
    text(x + 65, y + 432, "EXIT", 2, selected ? 0x2020f8 : 0xf82020);
    if (selected) {
        rectangle(x + 354, y + 229, 106, 25, 0x68f0ff);
        text(x + 382, y + 234, "EXIT", 2, 0x2020f8);
        rectangle(x + 182, y + 282, 168, 112, 0x68f0ff);
        text(x + 193, y + 321, "QUIT GAME", 2, 0x282828);
    }
    end_draw();
}

void frame() {
    const bool active = mode_select_active();
    const uint16_t pressed = uint16_t(~sio_get_pad_buttons_slot(0)) |
                             uint16_t(~sio_get_pad_buttons_slot(1));
    const unsigned mode = active ? psx_mod_read_byte(0x801f6330) : 0;
    const bool was_selected = menu.selected();
    const auto action = menu.update(active, mode, pressed);
    static const bool trace = std::getenv("NSN2_EXIT_TRACE") != nullptr;
    static uint16_t last_input = 0;
    if (trace && (pressed != last_input || was_selected != menu.selected())) {
        std::fprintf(stderr, "nsn2: Exit input active=%d mode=%u buttons=%04x selected=%d consume=%d\n",
                     int(active), mode, unsigned(pressed), int(menu.selected()), int(action.consume));
        std::fflush(stderr);
    }
    last_input = pressed;
    if (action.consume) {
        sio_set_pad_state_slot(0, 0xffff);
        sio_set_pad_state_slot(1, 0xffff);
        // MODESEL merges these active-high held/edge words at 0x800a3fbc.
        // A pad poll may already have completed before the host frame hook;
        // consume that latched sample too, so no navigation reaches the guest.
        static constexpr uint32_t pad_words[] = {0x801f5e00u, 0x801f5e02u, 0x801f5e80u, 0x801f5e82u};
        for (uint32_t address : pad_words)
            psx_mod_write_half(address, 0);
    }
    if (!was_selected && menu.selected()) std::fprintf(stderr, "nsn2: Exit selected\n");
    if (action.quit && !quit_queued) {
        SDL_Event event{};
        event.type = SDL_QUIT;
        quit_queued = SDL_PushEvent(&event) > 0;
        std::fprintf(stderr, "nsn2: Exit %s\n", quit_queued ? "requested" : "event failed");
    }
    if (active) draw_exit();
    else quit_queued = false;
}

} // namespace

extern "C" void nsn2_register_exit_menu(void) {
    static bool registered = false;
    if (!registered) {
        mod_register_frame_hook(frame);
        registered = true;
    }
}
