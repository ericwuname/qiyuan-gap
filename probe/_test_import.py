import sys; sys.path.insert(0, '.')
from brain.probe.normalizer import OnlineNormalizer
from brain.probe.world_model_db import WorldModelDB
from brain.probe.world_model import WorldModel
import os

print('All 3 modules imported OK')

n = OnlineNormalizer(dim=8)
print('Normalizer ready:', n.ready())

wm = WorldModel()
print('WorldModel status:', wm.get_status())

db_path = 'brain/probe/test_wm.db'
db = WorldModelDB(db_path)
print('DB pred count:', db.get_prediction_count())
db.close()
if os.path.exists(db_path):
    os.remove(db_path)

print('--- quick functional test ---')
# Test normalizer
for i in range(60):
    sv = [i*0.01, i*0.005, i*0.02, i*0.01, i*0.5, i*2.0, i*0.03, i*0.01]
    n.update(sv)
print('Normalizer ready after 60 updates:', n.ready())
norm = n.normalize([0.5, 0.3, 0.1, 0.2, 15.0, 60.0, 0.9, 0.3])
print('Normalized:', [round(v, 4) for v in norm])

# Test WorldModel predict
delta = wm.predict([0.5, 0.3, 0.1, 0.2, 15.0, 60.0, 0.9, 0.3], [1, 0, 0, 0, 0])
print('Delta prediction:', [round(v, 4) for v in delta])

print('ALL TESTS PASSED')
