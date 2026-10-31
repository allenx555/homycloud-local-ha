import unittest
from custom_components.homycloud_local.protocol.state import Sample
from custom_components.homycloud_local.protocol.feedback import confirmed, same_value
from custom_components.homycloud_local.protocol.cover import displayed_position, native_position


def sample(value, stamp=2, received=20):
    return Sample(value, stamp, 0, received)


class FeedbackTests(unittest.TestCase):
    def test_old_feedback_cannot_ack_a_new_command(self):
        self.assertFalse(confirmed({'switch':sample('true',received=9)},'switch',True,10,{}))
        self.assertTrue(confirmed({'switch':sample('true',received=11)},'switch',True,10,{}))

    def test_long_cover_travel_can_ack_progress_instead_of_endpoint(self):
        baseline={'percent_control':sample('30',1,5)}
        self.assertTrue(confirmed({'percent_control':sample('31')},'percent_control',99,10,baseline))
        self.assertFalse(confirmed({'percent_control':sample('29')},'percent_control',99,10,baseline))
        self.assertFalse(confirmed({'percent_control':sample('30')},'percent_control',99,10,baseline))

    def test_unchanged_cached_motion_does_not_ack(self):
        baseline={'control':sample('open',1,5)}
        self.assertFalse(confirmed({'control':sample('open',1)},'percent_control',99,10,baseline))
        self.assertTrue(confirmed({'control':sample('open',2)},'percent_control',99,10,baseline))

    def test_invalid_number_does_not_ack(self):
        self.assertFalse(same_value('nan',21))
        self.assertFalse(same_value('inf',21))
        self.assertTrue(same_value('21.0',21))

    def test_cover_direction_roundtrip(self):
        for inverted in [False,True]:
            for position in [0,25,50,75,100]:
                self.assertEqual(displayed_position(native_position(position,inverted),inverted),position)
        for raw in [None,'bad','nan',-1,101]:
            self.assertIsNone(displayed_position(raw))
        for raw in [True,-1,101,2.5]:
            with self.assertRaises(ValueError):native_position(raw)
