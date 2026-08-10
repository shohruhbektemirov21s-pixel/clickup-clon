"""Global DRF permission qatlami.

`READONLY_ALLOWED_CODES` (apps.core.access) faqat **ruxsat matritsasidan
o'tadigan** endpointlarni qamraydi. Matritsani umuman chaqirmaydigan yozish
yo'llari — parolni almashtirish, workspace'dan chiqish, kuzatuvchi bo'lish,
profilni tahrirlash, yangi workspace yaratish, taklifni qabul qilish — demo
hisob uchun ochiq qolar edi. Bu sinf shu bo'shliqni **fail-closed** yopadi:
ro'yxatga kiritilmagan HAR QANDAY yozish amali rad etiladi, ya'ni ertaga
qo'shiladigan endpoint avtomatik himoyalangan bo'ladi.
"""

from rest_framework.permissions import BasePermission

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

#: Faqat o'qish hisobiga ruxsat etilgan yagona yozish amallari. Ular sessiyaga
#: tegishli va hech qanday domen ma'lumotini o'zgartirmaydi.
READONLY_WRITE_ALLOWLIST = frozenset(
    {
        "auth-logout",  # o'z sessiyasini yopish
        "auth-refresh",  # tokenni yangilash
        "realtime-ticket",  # WebSocket handshake chiptasi
    }
)


class BlockReadonlyAccountWrites(BasePermission):
    """`User.is_readonly` hisoblari uchun har qanday yozish amalini bloklaydi."""

    message = "Demo hisob faqat o'qish uchun — bu amal bajarilmaydi."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if not getattr(request.user, "is_readonly", False):
            return True
        match = getattr(request, "resolver_match", None)
        return getattr(match, "url_name", None) in READONLY_WRITE_ALLOWLIST
