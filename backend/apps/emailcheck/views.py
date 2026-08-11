"""`POST workspaces/{id}/check-email/` — bitta manzilni tekshirish.

Bu endpoint tayinlash (assignee) tanlagichi uchun: foydalanuvchi email yozdi,
ish maydonida bunday a'zo yo'q — endi bu manzil umuman mavjudmi va uni
taklif qilishga arziydimi.

**Nega `member.invite` ruxsati talab qilinadi.** Endpoint server IP'sidan
begona MX serverlarga SMTP so'rov yuboradi. Uni har bir a'zoga ochish ikkita
narsani beradi: (a) begona domenlar bo'yicha manzil qidirish quroli, (b)
server IP'sini bloklanishga olib keladigan trafik. Manzilni tekshirish
faqat taklif yuborishdan OLDIN ma'noga ega, shuning uchun ruxsat ham
aynan o'sha.
"""

from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.access import require_membership_perm
from apps.emailcheck.service import verify_one
from apps.emailcheck.verifiers.base import STATUS_LABEL, EmailStatus, normalise
from apps.workspaces.models import Invitation, WorkspaceMember
from apps.core.enums import InvitationStatus


class CheckEmailSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254, trim_whitespace=True)


class CheckEmailView(APIView):
    """Manzilning holatini va ish maydoniga nisbatan o'rnini qaytaradi."""

    throttle_scope = "emailcheck"

    def get_throttles(self):
        return [ScopedRateThrottle()]

    def post(self, request, workspace_id):
        require_membership_perm(request.user, workspace_id, "member.invite")

        serializer = CheckEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = normalise(serializer.validated_data["email"])

        # Avval MAHALLIY holat: allaqachon a'zo bo'lsa yoki taklif kutilayotgan
        # bo'lsa, tashqi tekshiruvga umuman chiqmaymiz — javob shusiz ham
        # aniq, va bu bekorga SMTP so'rov yubormaslik demakdir.
        member = (
            WorkspaceMember.objects.filter(
                workspace_id=workspace_id, user__email__iexact=email
            )
            .select_related("user")
            .first()
        )
        if member is not None:
            return Response(
                {
                    "email": email,
                    "status": EmailStatus.VALID.value,
                    "status_label": STATUS_LABEL[EmailStatus.VALID],
                    "reason": "bu foydalanuvchi allaqachon ish maydoni a'zosi",
                    "membership": "member",
                    "user_id": str(member.user_id),
                    "full_name": member.user.full_name,
                    "role": member.role,
                }
            )

        pending = Invitation.objects.filter(
            workspace_id=workspace_id, email__iexact=email, status=InvitationStatus.PENDING
        ).first()

        result = verify_one(email)
        payload = {
            "email": result.email,
            "status": result.status.value,
            "status_label": STATUS_LABEL[result.status],
            "reason": result.reason,
            "checked_at": result.checked_at.isoformat().replace("+00:00", "Z"),
            "mx": result.mx_host,
            "provider": result.provider,
            "membership": "invited" if pending else "outside",
            "invitation_id": str(pending.id) if pending else None,
            # Ro'yxatdan o'tgan, lekin SHU ish maydonida yo'q foydalanuvchi —
            # taklif qabul qilinishi bilan darhol a'zo bo'ladi.
            "has_account": User.objects.filter(email__iexact=email).exists(),
        }
        return Response(payload, status=status.HTTP_200_OK)
