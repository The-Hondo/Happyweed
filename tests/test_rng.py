from happyweed.rng import PMRandom, low16_signed_abs, E_from_set_level, seed_from_E

def test_low16_signed_abs():
    assert low16_signed_abs(0x00008000) == 32768
    assert low16_signed_abs(0x0000FFFF) == 1
    assert low16_signed_abs(0x00000001) == 1

def test_E_mapping():
    # known equalities: 41-1 == 33-2 == 25-3 (all E=40)
    assert E_from_set_level(41,1) == 40
    assert E_from_set_level(33,2) == 40
    assert E_from_set_level(25,3) == 40
