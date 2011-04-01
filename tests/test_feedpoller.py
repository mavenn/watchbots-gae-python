import unittest2

class MyTest2(unittest2.TestCase):

  #def setUp(self):

  #def tearDown(self):
  
  def testMethod(self):
    self.assertEqual(1 + 2, 3, "1 + 2 not equal to 3")
