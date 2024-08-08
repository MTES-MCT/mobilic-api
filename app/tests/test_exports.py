from unittest import TestCase

from app.services.exports import get_buckets_params


class TestExports(TestCase):
    def test_small_request(self):
        nb_buckets, bucket_size = get_buckets_params(
            nb_users=30, nb_days=3, NxD_max=100
        )
        self.assertEqual(nb_buckets, 1)
        self.assertEqual(bucket_size, 30)

    def test_edge_case(self):
        nb_buckets, bucket_size = get_buckets_params(
            nb_users=50, nb_days=4, NxD_max=100
        )
        self.assertEqual(nb_buckets, 2)
        self.assertEqual(bucket_size, 25)

        nb_buckets, bucket_size = get_buckets_params(
            nb_users=25, nb_days=4, NxD_max=100
        )
        self.assertEqual(nb_buckets, 1)
        self.assertEqual(bucket_size, 25)

    def test_big_request(self):
        nb_buckets, bucket_size = get_buckets_params(
            nb_users=300, nb_days=72, NxD_max=2000
        )
        self.assertEqual(nb_buckets, 11)
        self.assertEqual(bucket_size, 28)
