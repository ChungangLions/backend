from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from .models import User, Like


class AccountsAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 사용자 생성
        cls.alice = User.objects.create_user(
            username="alice", password="pass1234", email="alice@example.com", user_role=User.Role.OWNER
        )
        cls.bob = User.objects.create_user(
            username="bob", password="pass1234", email="bob@example.com", user_role=User.Role.STUDENT_GROUP
        )
        cls.cara = User.objects.create_user(
            username="cara", password="pass1234", email="cara@example.com", user_role=User.Role.OWNER
        )

        # bob이 미리 받은 찜 하나 생성: cara -> bob
        Like.objects.create(user=cls.cara, target=cls.bob)

    def setUp(self):
        self.client = APIClient()

    # ---------- 사용자 조회 ----------
    def test_user_list_search_and_ordering(self):
        url = reverse("user-list")  # /api/accounts/users/
        # 검색
        resp = self.client.get(url, {"search": "ali"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        usernames = [u["username"] for u in resp.data]
        self.assertIn("alice", usernames)

        # 정렬 (받은 찜 수 내림차순)
        resp2 = self.client.get(url, {"ordering": "-likes_received_count"})
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        # bob은 cara에게서 1개 받은 상태 → bob이 상위에 있어야 함(간단 확인)
        self.assertGreaterEqual(resp2.data[0]["likes_received_count"], resp2.data[-1]["likes_received_count"])

    def test_user_retrieve(self):
        url = reverse("user-detail", args=[self.alice.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["username"], "alice")

    # ---------- 인증 요구 ----------
    def test_like_requires_auth(self):
        url = reverse("user-like", args=[self.bob.id])  # POST /users/{id}/like
        resp = self.client.post(url)  # 비인증
        print(f"Auth test response status: {resp.status_code}")
        print(f"Auth test response data: {resp.data}")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ---------- 찜 생성/중복 방지 ----------
    def test_like_create_and_duplicate_400(self):
        self.client.force_authenticate(user=self.alice)
        url = reverse("user-like", args=[self.bob.id])

        # 최초 생성
        resp = self.client.post(url)
        print(f"First response status: {resp.status_code}")
        print(f"First response data: {resp.data}")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Like.objects.filter(user=self.alice, target=self.bob).count(), 1)

        # 중복 생성 → 400 (UniqueConstraint 위배 → ValidationError 변환)
        resp2 = self.client.post(url)
        print(f"Second response status: {resp2.status_code}")
        print(f"Second response data: {resp2.data}")
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------- 자기 자신 찜 금지 ----------
    def test_like_self_forbidden(self):
        self.client.force_authenticate(user=self.alice)
        url = reverse("user-like", args=[self.alice.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("찜", str(resp.data).lower())  # 메시지 존재 정도만 확인

    # ---------- 찜 삭제 멱등 ----------
    def test_like_delete_idempotent(self):
        self.client.force_authenticate(user=self.alice)
        url = reverse("user-like", args=[self.bob.id])

        # 먼저 생성
        self.client.post(url)
        self.assertTrue(Like.objects.filter(user=self.alice, target=self.bob).exists())

        # 1차 삭제
        resp_del1 = self.client.delete(url)
        self.assertEqual(resp_del1.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Like.objects.filter(user=self.alice, target=self.bob).exists())

        # 2차 삭제(이미 없음) → 멱등 204
        resp_del2 = self.client.delete(url)
        self.assertEqual(resp_del2.status_code, status.HTTP_204_NO_CONTENT)

    # ---------- 토글: 생성(201) → 해제(200) ----------
    def test_like_toggle_like_then_unlike(self):
        self.client.force_authenticate(user=self.alice)
        url = reverse("user-like-toggle", args=[self.bob.id])  # POST

        # 없으면 생성
        resp1 = self.client.post(url)
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Like.objects.filter(user=self.alice, target=self.bob).exists())

        # 있으면 삭제
        resp2 = self.client.post(url)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertFalse(Like.objects.filter(user=self.alice, target=self.bob).exists())

    # ---------- Like 리소스 뷰셋: 목록 ----------
    def test_like_list_given_and_received(self):
        # alice -> bob 하나 만들어두고, cara -> bob은 setUpTestData에서 이미 존재
        Like.objects.get_or_create(user=self.alice, target=self.bob)

        # (1) 내가 누른 목록 (alice로 인증)
        self.client.force_authenticate(user=self.alice)
        url = reverse("like-list")  # /api/accounts/likes/
        resp_given = self.client.get(url)  # 기본: given
        self.assertEqual(resp_given.status_code, status.HTTP_200_OK)
        # alice가 누른 대상들만
        for row in resp_given.data:
            self.assertEqual(row["user"]["id"], self.alice.id)

        # (2) 내가 받은 목록 (bob으로 인증)
        self.client.force_authenticate(user=self.bob)
        resp_recv = self.client.get(url, {"mode": "received"})
        self.assertEqual(resp_recv.status_code, status.HTTP_200_OK)
        # bob을 타겟으로 한 레코드들만
        for row in resp_recv.data:
            self.assertEqual(row["target"]["id"], self.bob.id)
        # 최소 1개 이상(cara -> bob)
        self.assertGreaterEqual(len(resp_recv.data), 1)
