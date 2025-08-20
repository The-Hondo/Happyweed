# tests/test_player_walk.py
from happyweed.engine.player import (
    PlayerState, DIR_RIGHT, DIR_UP, DIR_LEFT, DIR_DOWN,
    set_desired, set_direction_immediate, update_player
)

# Build a tiny 20x12 with an interior corridor:
# - outer rim walls = 200
# - interior open = 10
# - add two blocking walls inside to test collision
def make_test_grid():
    W, H = 20, 12
    G = [[200]*W for _ in range(H)]
    for y in range(1, H-1):
        for x in range(1, W-1):
            G[y][x] = 10  # open
    # blockers
    G[6][10] = 200
    G[5][10] = 200
    return G

def test_buffered_turn_and_blocking():
    g = make_test_grid()
    # Start at (2,6), facing RIGHT
    st = PlayerState(x=2, y=6, dir=DIR_RIGHT, desired=None)

    # Walk forward 5 steps to (7,6)
    for _ in range(5):
        update_player(g, st)
    assert st.as_tuple() == (7,6)

    # Buffer an UP turn; cell above (7,5) is open, so it should turn and move
    set_desired(st, DIR_UP)
    update_player(g, st)
    assert st.as_tuple() == (7,5) and st.dir == DIR_UP

    # Continue up two more steps to (7,3)
    update_player(g, st)
    update_player(g, st)
    assert st.as_tuple() == (7,3)

    # Buffer RIGHT; target (8,3) is open, so turn+move in one tick
    set_desired(st, DIR_RIGHT)
    update_player(g, st)
    assert st.as_tuple() == (8,3) and st.dir == DIR_RIGHT

    # March right until we reach the vertical blocker at x=10 (y=3 is open; blocker is at y=5..6..)
    update_player(g, st)  # (9,3)
    update_player(g, st)  # (10,3)
    assert st.as_tuple() == (10,3)

    # Try to go DOWN into (10,4) [open], then (10,5) [blocked], then remain at (10,4)
    set_desired(st, DIR_DOWN)
    update_player(g, st)  # -> (10,4)
    assert st.as_tuple() == (10,4)
    update_player(g, st)  # forward DOWN blocked by wall at (10,5), so stay
    assert st.as_tuple() == (10,4)

    # Buffer LEFT while blocked; as soon as it's legal, move left
    set_desired(st, DIR_LEFT)
    update_player(g, st)  # -> (9,4)
    assert st.as_tuple() == (9,4) and st.dir == DIR_LEFT
