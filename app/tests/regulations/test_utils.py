from unittest import TestCase

from app.domain.regulations_helper import resolve_variables, DEFAULT_KEY
from app.models import Business
from app.models.business import TransportType, BusinessType

KEY = "KEY"
RES_SIMPLE = 10


class TestUtils(TestCase):
    def setUp(self):
        self.business_trm_long = Business(
            transport_type=TransportType.TRM,
            business_type=BusinessType.LONG_DISTANCE,
        )
        self.business_trv_frequent = Business(
            transport_type=TransportType.TRV,
            business_type=BusinessType.FREQUENT,
        )
        self.business_vtc = Business(
            transport_type=TransportType.TRV, business_type=BusinessType.VTC
        )
        self.dict_simple = {KEY: RES_SIMPLE}
        self.dict_granular = {
            KEY: {
                str(TransportType.TRM.name): {
                    str(BusinessType.LONG_DISTANCE.name): 1,
                    str(BusinessType.SHORT_DISTANCE.name): 2,
                },
                str(TransportType.TRV.name): 4,
            }
        }
        self.dict_default_value = {
            KEY: {
                str(TransportType.TRM.name): 1,
                str(TransportType.TRV.name): {
                    str(BusinessType.VTC.name): 2,
                    DEFAULT_KEY: 3,
                },
            }
        }

    def test_simple_dict(self):

        # when dict is very simple, i get the value whatever the business is
        res_trm = resolve_variables(
            dict_var=self.dict_simple, business=self.business_trm_long
        )
        self.assertEqual(res_trm[KEY], RES_SIMPLE)

        res_trv = resolve_variables(
            dict_var=self.dict_simple, business=self.business_trv_frequent
        )
        self.assertEqual(res_trv[KEY], RES_SIMPLE)

    def test_granular(self):
        res_trm = resolve_variables(
            dict_var=self.dict_granular, business=self.business_trm_long
        )
        self.assertEqual(res_trm[KEY], 1)

        res_trm = resolve_variables(
            dict_var=self.dict_granular, business=self.business_trv_frequent
        )
        self.assertEqual(res_trm[KEY], 4)

    def test_default_value(self):
        res_vtc = resolve_variables(
            dict_var=self.dict_default_value, business=self.business_vtc
        )
        self.assertEqual(res_vtc[KEY], 2)
        res_trv = resolve_variables(
            dict_var=self.dict_default_value,
            business=self.business_trv_frequent,
        )
        self.assertEqual(res_trv[KEY], 3)
