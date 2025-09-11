# https://dune.com/queries/1432505/2429301

count_avg = [
    (158_554.9, 1_668_001),
    (23_250.6, 135_325),
    (18_025.3, 165_385),
    (2_452.9, 15_151),
    (1_454.1, 19_527),
    (1_079.3, 10_818),
    (519.9, 7_171),
    (199.8, 951),
    (193.0, 1_392),
    (44.9, 531),
    (22.0, 118),
]

avg = sum([weighted for weighted, _ in count_avg]) / sum([count for _, count in count_avg])
print(avg)
slots_per_years = 365 * 3600 * 24 / 12
print("Average MEV upscaled with year:", avg * slots_per_years)