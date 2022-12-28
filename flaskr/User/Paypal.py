import sys
import os
from paypalcheckoutsdk.core import (SandboxEnvironment, LiveEnvironment,
                                    PayPalHttpClient)
from paypalcheckoutsdk.orders import OrdersGetRequest

CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
CLIENT_SECRET = os.getenv('PAYPAL_CLIENT_SECRET')


class PayPalClient:
    def __init__(self):
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        # SandBox Environment, Use Live Environment in Production
        self.environment = SandboxEnvironment(client_id=self.client_id,
                                              client_secret=self.client_secret)
        self.client = PayPalHttpClient(self.environment)

    def object_to_json(self, json_data):
        """
        Function to print all json data in an organized readable manner
        """

        result = {}
        if sys.version_info[0] < 3:
            itr = json_data.__dict__.iteritems()
        else:
            itr = json_data.__dict__.items()
        for key, value in itr:
            # Skip internal attributes.
            if key.startswith("__"):
                continue
            result[key] = self.array_to_json_array(value) if isinstance(value, list) else \
                self.object_to_json(value) if not self.is_primittive(value) else value
        return result

    def array_to_json_array(self, json_array):
        result = []
        if isinstance(json_array, list):
            for item in json_array:
                result.append(self.object_to_json(item) if not self.is_primittive(item)
                              else self.array_to_json_array(item) if isinstance(item, list) else item)
        return result

    @staticmethod
    def is_primittive(data):
        return isinstance(data, str) or isinstance(data, int)


class GetOrder(PayPalClient):

    def get_order(self, order_id):
        """Method To Get Order"""
        request = OrdersGetRequest(order_id=order_id)
        response = self.client.execute(request=request)

        return response.result
