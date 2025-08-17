from happyweed.tiles import wall_for_level, superdrug_for_level

def test_wall_fallback():
    assert wall_for_level(20) == 220
    assert wall_for_level(21) == 255
    assert wall_for_level(25) == 255

def test_super_fallback():
    assert superdrug_for_level(14) == 94
    assert superdrug_for_level(15) == 255
    assert superdrug_for_level(25) == 255
