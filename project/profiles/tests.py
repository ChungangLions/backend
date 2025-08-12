from datetime import date, timedelta

from django.urls import reverse
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings as dj_settings

from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import User
from .models import (
    OwnerProfile, OwnerPhoto, Menu,
    StudentGroupProfile, StudentPhoto, StudentProfile,
    BusinessType, PartnershipGoal, Service,
)


def valid_image(name="img.png"):
    """
    Pillow가 있으면 2x2 PNG를 만들어서 보내고,
    없으면 1x1 GIF 바이트로 대체한다.
    """
    try:
        from PIL import Image
        import io
        buf = io.BytesIO()
        Image.new("RGB", (2, 2), (255, 0, 0)).save(buf, format="PNG")
        buf.seek(0)
        return SimpleUploadedFile(name, buf.read(), content_type="image/png")
    except Exception:
        # Pillow가 없으면 유효한 1x1 GIF 사용
        data = (
            b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
            b"\x00\x02\x02L\x01\x00;"
        )
        return SimpleUploadedFile("img.gif", data, content_type="image/gif")


class ProfilesAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 기본 대표사진 경로가 없으면 주입 (OwnerProfile 생성 시 사용될 수 있음)
        if not hasattr(dj_settings, "DEFAULT_OWNER_PHOTO_PATH"):
            setattr(dj_settings, "DEFAULT_OWNER_PHOTO_PATH", "owner_profile/photos/default.jpg")

        # 유저 3명
        cls.owner1 = User.objects.create_user(username="owner1", email="o1@example.com", password="pw1234")
        cls.owner2 = User.objects.create_user(username="owner2", email="o2@example.com", password="pw1234")
        cls.group1 = User.objects.create_user(username="group1", email="g1@example.com", password="pw1234")
        cls.student1 = User.objects.create_user(username="student1", email="s1@example.com", password="pw1234")

        # OwnerProfile 2개(리스트/필터/권한 테스트용)
        cls.op1 = OwnerProfile.objects.create(
            user=cls.owner1,
            campus_name="중앙대",
            business_type=BusinessType.RESTAURANT,
            profile_name="맛집1",
            business_day={"mon": ["09:00-18:00"]},
            partnership_goal=PartnershipGoal.NEW_CUSTOMERS,
            partnership_goal_other="",
            average_sales=12000,
            margin_rate="30.00",
            peak_time=["12:00-13:00"],
            off_peak_time=[],
            available_service=Service.DRINK,
            available_service_other="",
            partnership_type=["할인형"],
            comment="환영합니다",
        )
        cls.op2 = OwnerProfile.objects.create(
            user=cls.owner2,
            campus_name="한양대",
            business_type=BusinessType.CAFE,
            profile_name="카페2",
            business_day={"mon": ["10:00-19:00"]},
            partnership_goal=PartnershipGoal.REVISIT,
            partnership_goal_other="",
            average_sales=9000,
            margin_rate="25.00",
            peak_time=[],
            off_peak_time=[],
            available_service=Service.SIDE_MENU,
            available_service_other="",
            partnership_type=["리뷰형"],
            comment="어서오세요",
        )

        # StudentGroupProfile(상세/권한/사진 테스트용)
        today = date.today()
        cls.sgp1 = StudentGroupProfile.objects.create(
            user=cls.group1,
            university_name="서울대",
            council_name="총학생회",
            position="회장",
            student_size=3000,
            term_start=today,
            term_end=today + timedelta(days=365),
            partnership_start=today,
            partnership_end=today + timedelta(days=180),
        )

        # StudentProfile(상세/수정/삭제 테스트용)
        cls.sp1 = StudentProfile.objects.create(
            user=cls.student1,
            university_name="고려대",
        )

    def setUp(self):
        self.client = APIClient()

    # ---------------------------
    # 공통: 인증 요구 확인
    # ---------------------------
    def test_auth_required_on_lists(self):
        # Owner list
        url = reverse("profiles:owner-list")
        self.assertIn(self.client.get(url).status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        # Student-group list
        url = reverse("profiles:student-group-list")
        self.assertIn(self.client.get(url).status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        # Student list
        url = reverse("profiles:student-list")
        self.assertIn(self.client.get(url).status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    # ---------------------------
    # OwnerProfile: 목록/필터/생성
    # ---------------------------
    def test_owner_list_and_filter(self):
        self.client.force_authenticate(self.owner1)
        url = reverse("profiles:owner-list")

        # 전체
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [row["profile_name"] for row in resp.data]
        self.assertIn("맛집1", names)
        self.assertIn("카페2", names)

        # 업종 필터
        resp2 = self.client.get(url, {"business_type": BusinessType.RESTAURANT})
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertTrue(all(r["business_type"] == BusinessType.RESTAURANT for r in resp2.data))

    def test_owner_create_success_and_validations(self):
        self.client.force_authenticate(self.owner2)
        url = reverse("profiles:owner-list")

        # 성공
        payload_ok = {
            "campus_name": "건국대",
            "business_type": BusinessType.RESTAURANT,
            "profile_name": "새맛집",
            "business_day": {"tue": ["09:00-18:00"]},
            "partnership_goal": PartnershipGoal.NEW_CUSTOMERS,
            "average_sales": 15000,
            "margin_rate": "33.50",
            "peak_time": [],
            "off_peak_time": [],
            "available_service": Service.DRINK,
            "comment": "좋은 가게",
            "partnership_type": ["할인형"],
        }
        resp = self.client.post(url, data=payload_ok, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["user"], self.owner2.id)
        self.assertEqual(resp.data["profile_name"], "새맛집")

        # 유효성: margin_rate 범위
        bad_margin = {**payload_ok, "profile_name": "나쁜마진", "margin_rate": "150.00"}
        resp2 = self.client.post(url, data=bad_margin, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("margin_rate", resp2.data)

        # 유효성: partnership_goal=OTHER 시 상세 필수
        other_goal = {
            **payload_ok,
            "profile_name": "기타목표",
            "partnership_goal": PartnershipGoal.OTHER,
            "partnership_goal_other": "",
        }
        resp3 = self.client.post(url, data=other_goal, format="json")
        self.assertEqual(resp3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("partnership_goal_other", resp3.data)

        # 유효성: available_service=OTHER 시 상세 필수
        other_service = {
            **payload_ok,
            "profile_name": "기타서비스",
            "available_service": Service.OTHER,
            "available_service_other": "",
        }
        resp4 = self.client.post(url, data=other_service, format="json")
        self.assertEqual(resp4.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("available_service_other", resp4.data)

    # ---------------------------
    # OwnerProfile: 상세/수정/삭제 + 권한
    # ---------------------------
    def test_owner_retrieve_patch_delete_and_permission(self):
        # 조회
        self.client.force_authenticate(self.owner1)
        url_detail = reverse("profiles:owner-detail", args=[self.op1.id])
        resp = self.client.get(url_detail)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["profile_name"], "맛집1")

        # 권한: 다른 유저는 수정 금지
        self.client.force_authenticate(self.owner2)
        resp_forbidden = self.client.patch(url_detail, {"comment": "수정시도"}, format="json")
        self.assertEqual(resp_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # 소유자는 수정 가능
        self.client.force_authenticate(self.owner1)
        resp_ok = self.client.patch(url_detail, {"comment": "바뀐코멘트"}, format="json")
        self.assertEqual(resp_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_ok.data["comment"], "바뀐코멘트")

        # 삭제
        resp_del = self.client.delete(url_detail)
        self.assertEqual(resp_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(OwnerProfile.objects.filter(id=self.op1.id).exists())

    # ---------------------------
    # OwnerPhoto: 추가/삭제 + 권한
    # ---------------------------
    def test_owner_photo_add_and_delete(self):
        self.client.force_authenticate(self.owner2)

        # 사진 추가
        url_add = reverse("profiles:owner-photo-list", args=[self.op2.id])
        resp_add = self.client.post(url_add, {"image": valid_image()}, format="multipart")
        self.assertEqual(resp_add.status_code, status.HTTP_201_CREATED)
        photo_id = resp_add.data["id"]
        self.assertTrue(OwnerPhoto.objects.filter(id=photo_id, owner_profile=self.op2).exists())

        # 다른 유저는 삭제 금지
        self.client.force_authenticate(self.owner1)
        url_del = reverse("profiles:owner-photo-detail", args=[self.op2.id, photo_id])
        resp_forbidden = self.client.delete(url_del)
        self.assertEqual(resp_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # 소유자는 삭제 가능
        self.client.force_authenticate(self.owner2)
        resp_del = self.client.delete(url_del)
        self.assertEqual(resp_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(OwnerPhoto.objects.filter(id=photo_id).exists())

    # ---------------------------
    # Menu: 목록/추가/수정/삭제
    # ---------------------------
    def test_menu_crud(self):
        self.client.force_authenticate(self.owner2)

