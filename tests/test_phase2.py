import unittest
from cloud.os_engine import fcfs, priority_nonpreemptive, round_robin, bankers_safety

class Phase2Tests(unittest.TestCase):
    def setUp(self):
        self.ps=[{"pid":"P1","arrival":0,"burst":5,"priority":2},{"pid":"P2","arrival":1,"burst":3,"priority":1},{"pid":"P3","arrival":2,"burst":1,"priority":3}]
    def test_fcfs_metrics(self):
        r=fcfs(self.ps); self.assertEqual([x["pid"] for x in r["schedule"]],["P1","P2","P3"]); self.assertEqual(r["average_waiting"],3.33)
    def test_priority_order(self):
        r=priority_nonpreemptive(self.ps); self.assertEqual([x["pid"] for x in r["schedule"]],["P1","P2","P3"])
    def test_round_robin_completes_all(self):
        r=round_robin(self.ps,2); self.assertEqual({x["pid"] for x in r["processes"]},{"P1","P2","P3"}); self.assertEqual(sum(p["burst"] for p in self.ps),sum(s["end"]-s["start"] for s in r["schedule"] if s["pid"]))
    def test_bankers_safe(self):
        r=bankers_safety([3,3,2],[[0,1,0],[2,0,0],[3,0,2],[2,1,1],[0,0,2]],[[7,5,3],[3,2,2],[9,0,2],[2,2,2],[4,3,3]])
        self.assertTrue(r["safe"]); self.assertEqual(len(r["safe_sequence"]),5)
    def test_bankers_unsafe(self):
        self.assertFalse(bankers_safety([0],[[1],[1]],[[2],[2]])["safe"])
    def test_invalid_quantum(self):
        with self.assertRaises(ValueError): round_robin(self.ps,0)
        with self.assertRaises(ValueError): round_robin(self.ps,2.5)
        with self.assertRaises(ValueError): round_robin(self.ps,"bad")
    def test_invalid_process_shape(self):
        with self.assertRaises(ValueError): fcfs(["not-a-process-object"])
        with self.assertRaises(ValueError): fcfs([{"pid": ["unhashable"], "burst": 1}])
    def test_banker_rejects_non_integer_values(self):
        with self.assertRaises(ValueError): bankers_safety([1.5], [[0]], [[1]])

if __name__=="__main__": unittest.main()
