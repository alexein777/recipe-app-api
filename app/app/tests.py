from django.test import SimpleTestCase
from app import calc


class CalcTests(SimpleTestCase):
    def test_add(self):
        res = calc.add(5, 6)
        self.assertEqual(res, 11)

    def test_sub(self):
        res = calc.sub(10, 4)
        self.assertEqual(res, 6)

    def test_mul(self):
        res = calc.mul(3, 4)
        self.assertEqual(res, 12)

    def test_div(self):
        res = calc.div(18, 6)
        self.assertEqual(res, 3)

    def test_truediv(self):
        res = calc.truediv(9, 2)
        self.assertEqual(res, 4.5)
