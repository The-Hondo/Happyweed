# tests/test_runtime_collisions.py
from happyweed.engine.collisions import (
    RuntimeOverlay, classify_tile, is_passable_runtime,
    on_enter_player, on_enter_cop, on_super_kill_player, FLOOR_SUBSTRATE
)

def test_classify_open_exit_jail_rules():
    # Open floor
    assert classify_tile(10, False) >= 2
    assert classify_tile(199, False) >= 2
    # Exit band always passable
    for t in range(241, 250):
        assert classify_tile(t, False) >= 2
    # Jail: player blocked, cop allowed
    assert classify_tile(250, False) < 2
    assert classify_tile(250, True) >= 2

def test_super_255_is_passable_only_where_overlay_marks():
    overlay = RuntimeOverlay(super_positions={(5, 5)})
    # Same tile id (255) — passable only at (5,5)
    assert is_passable_runtime("player", 255, 5, 5, overlay) is True
    assert is_passable_runtime("player", 255, 6, 5, overlay) is False
    # Cop doesn't get special handling for 255; overlay only affects player stepping there
    assert is_passable_runtime("cop", 255, 5, 5, overlay) is True  # jail pass-through could allow, but map uses 255 as wall except super
    assert is_passable_runtime("cop", 255, 6, 5, overlay) is True  # cops can traverse jail/walls>=250 per modeB; movement AI will constrain

def test_leaf_pickup_writes_180_and_flags():
    grid = [[0]*3 for _ in range(3)]
    grid[1][1] = 80
    overlay = RuntimeOverlay()
    ev = on_enter_player(80, 1, 1, level=8, overlay=overlay, grid=grid)
    assert ev["leaf_collected"] and not ev["super_collected"]
    assert grid[1][1] == FLOOR_SUBSTRATE

def test_super_pickup_writes_180_and_flags_early_levels():
    grid = [[0]*3 for _ in range(3)]
    level = 12
    grid[1][1] = 80 + level
    overlay = RuntimeOverlay()
    ev = on_enter_player(80 + level, 1, 1, level=level, overlay=overlay, grid=grid)
    assert ev["super_collected"]
    assert grid[1][1] == FLOOR_SUBSTRATE

def test_super_pickup_writes_180_and_flags_late_levels_255():
    grid = [[0]*3 for _ in range(3)]
    level = 21
    grid[1][1] = 255  # wall everywhere EXCEPT where overlay says there's a super
    overlay = RuntimeOverlay(super_positions={(1, 1)})
    ev = on_enter_player(255, 1, 1, level=level, overlay=overlay, grid=grid)
    assert ev["super_collected"]
    assert grid[1][1] == FLOOR_SUBSTRATE
    assert (1, 1) not in overlay.super_positions  # consumed

def test_exit_touch_event_does_not_mutate_map():
    grid = [[0]*3 for _ in range(3)]
    grid[1][1] = 241
    overlay = RuntimeOverlay()
    ev = on_enter_player(241, 1, 1, level=5, overlay=overlay, grid=grid)
    assert ev["exit_touched"] and not ev["leaf_collected"] and not ev["super_collected"]
    assert grid[1][1] == 241

def test_scoring_bug_points_only_for_single_cop_stack():
    overlay = RuntimeOverlay()
    pts1 = on_super_kill_player(4, 4, n_cops_on_tile=1, overlay=overlay)
    pts2 = on_super_kill_player(4, 4, n_cops_on_tile=2, overlay=overlay)
    pts3 = on_super_kill_player(4, 4, n_cops_on_tile=3, overlay=overlay)
    assert pts1 == 500
    assert pts2 == 0 and pts3 == 0
    # Visual frames still reflect the count (181..184)
    fx = overlay.score_fx[(4, 4)]
    assert 1 <= fx["frame"] <= 4 and fx["timer"] > 0
