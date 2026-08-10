# Granular Ruxsatlar Matritsasi, Space-darajali Assignment va Invite-Register — Dizayn Hujjati

**Status: binding spetsifikatsiya — implementatsiya shu hujjatga qat'iy amal qiladi**
**Versiya:** 2.0.0 · **Sana:** 2026-08-10
<!-- 2026-08-10: "2.0.0-draft" + "binding" bir vaqtda turgan edi. Hujjat
     implementatsiya qilingan va kod unga amal qiladi, shuning uchun `-draft`
     olib tashlandi: `binding` bo'lgan hujjat draft bo'la olmaydi. -->
**Upstream:** `docs/API_CONTRACT.md` v1.0.0, `docs/DATA_MODEL.md`, `CLAUDE.md`
**Downstream:** `API_CONTRACT.md` → v1.1.0 (§17 ga R18–R23 qo'shiladi)

---

## 0. Arxitektura qarorlari (o'zgartirmang)

| # | Qaror | Sabab |
|---|---|---|
| **AD-1** | Ruxsat **katalogi kodda** (`apps/core/permissions.py`), **grantlar DB'da** (`RolePermission`). Katalog jadval EMAS. | Yangi kod = 1 qator Python, migratsiyasiz. |
| **AD-2** | `has_perm` = `DEFAULT_MATRIX[role]` ustiga workspace override'lari. Qator yo'q bo'lsa **defaultga qaytadi**. | Yangi kodlar backfillsiz ishlaydi. |
| **AD-3** | `owner` hech qachon `RolePermission` jadvalida saqlanmaydi: `role == owner → True` short-circuit + DB `CheckConstraint(role != 'owner')`. | Owner lock'ini DB darajasida buzib bo'lmaydi. |
| **AD-4** | Cache kaliti `wsperm:{workspace_id}:{workspace.permissions_version}`. | Invalidatsiya bir zumda, cross-process, qo'shimcha querysiz. |
| **AD-5** | Matritsa **monoton**: `guest ⊆ member ⊆ admin ⊆ owner`. Buzilsa `400`. | Kontraktdagi rol modelini saqlaydi. |
| **AD-6** | PM/loyiha biriktiruvi `SpaceMember` jadvali orqali (DATA_MODEL D8 bekor). | Talab: PM loyihaga odam biriktiradi. |
| **AD-7** *(v1.3.0 da tuzatildi)* | Task'ga assign qilinganda `SpaceMember(access=viewer, source=auto_assignee)` **faqat bo'limni hali ko'ra olmaydigan** foydalanuvchi uchun yaratiladi. | "Oddiy user o'ziga berilgan tasklarni boshidanoq ko'radi". **Shartsiz yozish xato edi:** §B.5 bo'yicha `viewer` eng past huquq va workspace rolidan ustun turadi, ya'ni ochiq bo'limda vazifa biriktirilgan mehmon yoki admin o'sha vazifani tahrirlay olmay qolardi (`task.update_assigned` → 403). Endi qator faqat **ko'rinish qo'shadi**, hech qachon vakolat olib qo'ymaydi — migratsiya 0004 backfill qoidasi bilan bir xil. |
| **AD-8** | `ROLE_RANK` **o'chirilmaydi** — roster tartibi, monotonlik, rol-o'zgartirish vakolati, oxirgi-owner qoidalari uchun qoladi. | Xavfsizlik invariantlari matritsa orqali buzilmasin. |
| **AD-9** | `DEFAULT_MATRIX` bugungi `API_CONTRACT.md §1.7` xatti-harakatini **bit-ma-bit** takrorlaydi. | Mavjud testlar o'zgarishsiz o'tishi — regressiya detektori. |

---

## A. Ruxsat katalogi

Kod formati: `<resource>.<action>`, `[a-z_]+\.[a-z_]+`, max 64 belgi. Kodlar **o'chirilmaydi**, faqat `deprecated=True`.

```python
# apps/core/permissions.py
@dataclass(frozen=True)
class PermissionDef:
    code: str
    group: str
    label: str          # o'zbekcha UI yorlig'i
    description: str    # o'zbekcha tavsif
    defaults: frozenset[str]   # {"admin","member"} — owner HECH QACHON bu yerda emas
    owner_only: bool = False   # hech qachon grant qilinmaydi (400)
    sensitive: bool = False    # UI ogohlantirish
    deprecated: bool = False
```

**O**=owner (doim ✔, lock), **A**=admin, **M**=member, **G**=guest — bular **default**.

> **2026-08 siyosati (katalog v3, BINDING).** `member` ustuni qisqartirildi:
> a'zo **ko'radi va o'ziga biriktirilganini bajaradi**. `member` dan olib
> tashlangan kodlar: `task.update`, `task.delete`, `task.move`, `task.assign`,
> `folder.create/update/delete`, `list.create/update/delete/move`,
> `tag.update`, `tag.delete`. `member` da qolganlari (14 kod):
> `workspace.read`, `member.read`, `space.read`, `task.read`, `task.create`,
> `task.update_assigned`, `task.watch`, `comment.create`,
> `comment.update_own`, `comment.delete_own`, `attachment.read`,
> `attachment.create`, `attachment.delete_own`, `tag.create`.
> `admin`, `guest` va `owner` ustunlariga **tegilmadi**. Monotonlik saqlanadi:
> guest (9) ⊆ member (14) ⊆ admin (44) ⊆ owner (48). *(v4/v5 dan keyin: guest 10, member 14, admin 45, owner 49.)*
>
> **"Loyiha menejeri" alohida workspace roli emas.** U bo'lim darajasidagi
> `SpaceAccess.MANAGER` (`SPACE_MANAGER_GRANTS`, §B.5/§F-5) — yuqorida olib
> tashlangan kodlar PM ga **faqat o'z bo'limi ichida** lokal qaytariladi.
> `space.delete`, `member.*`, `workspace.*`, `tag.*` PM ga hech qachon o'tmaydi.
> CI: `apps/core/tests/test_permission_policy.py`.
>
> **2026-08 (katalog v4) — jamoa ko'rinishi.** `member.read` `guest` ga ham
> berildi: a'zolar ro'yxati (`GET workspaces/{id}/members/`) va a'zo profili
> (`members/{uid}/profile/`) endi **hamma** rollarga ochiq. Guest 9 → **10**
> kod; monotonlik saqlanadi (yuqori rollarda kod allaqachon bor edi).
>
> **Bunga bog'liq majburiy himoya (AppSec O-1).**
> `apps.accounts.serializers.UserSummarySerializer` mehmonga **begona `email`
> o'rniga `null`** qaytaradi (o'z emaili ko'rinadi). Sabab: mehmon ko'pincha
> tashqi kontraktor/mijoz — roster + assignee + izoh muallifi orqali u bitta
> so'rovda butun jamoaning ish emaillarini yig'ib olardi (targeted phishing
> uchun tayyor ro'yxat). Kontrakt §1.7 rosterni aynan shu sababdan yopgan edi,
> shuning uchun rosterni ochishda himoya serializer qatlamiga ko'chirildi.
> Chaqiruvchining roli `require_membership()` `request.user` ga yozib
> qo'yadigan `_current_membership` orqali olinadi (`remember_membership`) —
> har bir view'ga `context` uzatish shart emas, ya'ni "bitta joyni unutdim →
> email sizdi" xatosi tuzilmaviy ravishda mumkin emas.
>
> **2026-08 (katalog v5) — `space.change_visibility` (AppSec).** Bo'limning
> `is_private` bayrog'i `space.update` dan **ajratildi**. Sabab: `space.update`
> `SPACE_MANAGER_GRANTS` ichida, ya'ni bo'lim menejeri (PM) `PATCH spaces/{id}/`
> bilan yopiq loyihaning butun mazmunini bir so'rovda barcha ish maydoni
> a'zolariga ocha olardi (yoki teskarisi — ochiq bo'limni yopib, unga tayangan
> mehmon/kontraktorlarni chiqarib yuborardi). Yangi kod `admin` default'da,
> `sensitive=True`, va `space.delete` bilan bir xil mantiqda
> `SPACE_MANAGER_GRANTS` ga **kirmaydi**. Kodlar 48 → **49**, admin 44 → **45**.
> `member`/`guest` ustunlariga tegilmadi, monotonlik saqlanadi.
>
> **Migratsiya SHART EMAS.** `_build_matrix()` `DEFAULT_MATRIX` dan boshlanadi
> va DB qatorlarini ustiga yopishtiradi; yangi kod uchun `RolePermission`
> qatori YO'Q → default (`admin`) amal qiladi. `ensure_role_permissions()`
> (bootstrap + `role-permissions/` resolver fallback + admin action) qatorni
> keyinroq lazily materializatsiya qiladi. Migratsiya 0003/0005 tarixiy
> snapshot bo'lgani uchun ularga tegilmaydi.

### Guruh `workspace` — Ish maydoni
| Kod | Tavsif | O | A | M | G | Flag |
|---|---|:-:|:-:|:-:|:-:|---|
| `workspace.read` | Ish maydoni va daraxtni o'qish | ✔ | ✔ | ✔ | ✔ | |
| `workspace.update` | Nom/tavsif/rangni o'zgartirish | ✔ | ✕ | ✕ | ✕ | |
| `workspace.delete` | Ish maydonini o'chirish | ✔ | ✕ | ✕ | ✕ | sensitive |
| `workspace.manage_permissions` | Matritsani o'qish/yozish | ✔ | ✕ | ✕ | ✕ | **owner_only** |
| `workspace.transfer_ownership` | Egalikni berish | ✔ | ✕ | ✕ | ✕ | **owner_only** |

### Guruh `member` — A'zolar va takliflar
| Kod | Tavsif | O | A | M | G |
|---|---|:-:|:-:|:-:|:-:|
| `member.read` | A'zolar ro'yxati va profillari | ✔ | ✔ | ✔ | ✔ |
| `member.invite` | Taklif yuborish | ✔ | ✔ | ✕ | ✕ |
| `member.remove` | A'zoni chiqarish | ✔ | ✔ | ✕ | ✕ |
| `member.role_change` | Rolni o'zgartirish | ✔ | ✔ | ✕ | ✕ |
| `invitation.read` | Takliflar ro'yxati | ✔ | ✔ | ✕ | ✕ |
| `invitation.manage` | Bekor qilish / qayta yuborish | ✔ | ✔ | ✕ | ✕ |

### Guruh `space` — Bo'limlar
| Kod | Tavsif | O | A | M | G |
|---|---|:-:|:-:|:-:|:-:|
| `space.read` | Ochiq bo'limlarni ko'rish | ✔ | ✔ | ✔ | ✔ |
| `space.read_private` | Barcha yopiq bo'limlarni `SpaceMember`siz ko'rish | ✔ | ✔ | ✕ | ✕ |
| `space.create` | Bo'lim yaratish | ✔ | ✔ | ✕ | ✕ |
| `space.update` | Bo'limni tahrirlash/arxivlash | ✔ | ✔ | ✕ | ✕ |
| `space.change_visibility` | **`is_private` ni o'zgartirish** (sensitive) | ✔ | ✔ | ✕ | ✕ |
| `space.delete` | Bo'limni o'chirish | ✔ | ✔ | ✕ | ✕ |
| `space.manage_members` | **PM huquqi:** bo'limga odam biriktirish | ✔ | ✔ | ✕ | ✕ |
| `space.manage_statuses` | Status to'plamini almashtirish | ✔ | ✔ | ✕ | ✕ |

### Guruh `folder` — Jildlar
| Kod | O | A | M | G |
|---|:-:|:-:|:-:|:-:|
| `folder.create` | ✔ | ✔ | ✕ | ✕ |
| `folder.update` | ✔ | ✔ | ✕ | ✕ |
| `folder.delete` (`?strategy=detach`) | ✔ | ✔ | ✕ | ✕ |
| `folder.delete_cascade` (`?strategy=cascade`) | ✔ | ✔ | ✕ | ✕ |

### Guruh `list` — Ro'yxatlar
| Kod | O | A | M | G |
|---|:-:|:-:|:-:|:-:|
| `list.create` | ✔ | ✔ | ✕ | ✕ |
| `list.update` | ✔ | ✔ | ✕ | ✕ |
| `list.delete` | ✔ | ✔ | ✕ | ✕ |
| `list.move` | ✔ | ✔ | ✕ | ✕ |
| `list.manage_statuses` | ✔ | ✔ | ✕ | ✕ |

### Guruh `task` — Vazifalar
| Kod | Tavsif | O | A | M | G |
|---|---|:-:|:-:|:-:|:-:|
| `task.read` | Vazifalarni o'qish | ✔ | ✔ | ✔ | ✔ |
| `task.create` | Vazifa yaratish | ✔ | ✔ | ✔ | ✕ |
| `task.update` | **Har qanday** vazifani tahrirlash | ✔ | ✔ | ✕ | ✕ |
| `task.update_assigned` | **Faqat o'ziga biriktirilganini** tahrirlash/ko'chirish | ✔ | ✔ | ✔ | ✔ |
| `task.delete` | Soft delete | ✔ | ✔ | ✕ | ✕ |
| `task.move` | Har qanday vazifani ko'chirish | ✔ | ✔ | ✕ | ✕ |
| `task.assign` | `assignee_ids` o'zgartirish | ✔ | ✔ | ✕ | ✕ |
| `task.watch` | Kuzatuvchi bo'lish | ✔ | ✔ | ✔ | ✔ |
| `task.restore` | Tiklash | ✔ | ✔ | ✕ | ✕ |
| `task.view_deleted` | `?include_deleted=true` | ✔ | ✔ | ✕ | ✕ |

> **Rezolyutsiya tartibi (BINDING):** `PATCH tasks/{id}/` va `…/move/` — avval `task.update`/`task.move`; yo'q bo'lsa `task.update_assigned` **va** chaqiruvchi `TaskAssignee` qatoriga ega bo'lsa ruxsat; aks holda `403`. Bu bugungi `require_task_editor()` mantiqini aynan takrorlaydi.

### Guruh `comment` — Izohlar
| Kod | O | A | M | G |
|---|:-:|:-:|:-:|:-:|
| `comment.create` | ✔ | ✔ | ✔ | ✔ |
| `comment.update_own` | ✔ | ✔ | ✔ | ✔ |
| `comment.delete_own` | ✔ | ✔ | ✔ | ✔ |
| `comment.delete_any` | ✔ | ✔ | ✕ | ✕ |

> Kontrakt §12: **hech kim** (owner ham) boshqaning izohini tahrirlay olmaydi — `comment.update_any` kodi ataylab **mavjud emas**.

### Guruh `attachment` — Biriktirmalar
| Kod | Tavsif | O | A | M | G |
|---|---|:-:|:-:|:-:|:-:|
| `attachment.read` | Biriktirmalar ro'yxatini ko'rish va yuklab olish | ✔ | ✔ | ✔ | ✔ |
| `attachment.create` | Vazifaga fayl biriktirish | ✔ | ✔ | ✔ | ✕ |
| `attachment.delete_own` | O'zi yuklagan faylni o'chirish | ✔ | ✔ | ✔ | ✕ |
| `attachment.delete_any` | **Boshqaning faylini o'chirish** (moderatsiya, sensitive) | ✔ | ✔ | ✕ | ✕ |

> Bu guruh katalog v2 da qo'shilgan, lekin §A jadvallariga hech qachon
> yozilmagan — "9 guruh" deb yozilib, 8 tasi ko'rsatilib turgan edi.
> `attachment.delete_any` — `comment.delete_any` bilan bir xil naqsh: egasi
> `*_own` bilan o'chiradi, moderator `*_any` bilan. Ikkalasi ham
> `SPACE_MANAGER_GRANTS` ga **kirmaydi**: moderatsiya huquqi bo'lim menejeriga
> lokal berilmaydi (`apps/core/access.py`).
>
> **Bajarilgan vazifaga ham fayl biriktiriladi** (kontrakt R24): biriktirma
> endpointlari `completed_at` / `status.type` ni umuman tekshirmaydi.

### Guruh `tag` — Teglar
| Kod | O | A | M | G |
|---|:-:|:-:|:-:|:-:|
| `tag.create` | ✔ | ✔ | ✔ | ✕ |
| `tag.update` | ✔ | ✔ | ✕ | ✕ |
| `tag.delete` | ✔ | ✔ | ✕ | ✕ |

**Jami: 49 kod, 9 guruh** (v2 da `attachment` guruhi, v5 da `space.change_visibility` qo'shilgan). Defaultlar monotonlik shartini qanoatlantiradi — CI testi `test_default_matrix_is_monotonic` tekshiradi; aniq ro'yxatni `test_member_defaults_are_exactly_the_policy_set` qulflaydi.

---

## B. Ma'lumotlar modeli

### B.1 Yangi enum'lar — `apps/core/enums.py`

```python
class AssignableRole(models.TextChoices):
    """RolePermission jadvalida saqlanadigan rollar. owner YO'Q."""
    ADMIN = "admin", "Admin"
    MEMBER = "member", "A'zo"
    GUEST = "guest", "Mehmon"


class SpaceAccess(models.TextChoices):
    VIEWER = "viewer", "Ko'ruvchi"              # faqat o'qish
    CONTRIBUTOR = "contributor", "Ishtirokchi"  # workspace roli bo'yicha yozish
    MANAGER = "manager", "Menejer (PM)"         # + lokal space.manage_members


class SpaceMemberSource(models.TextChoices):
    MANUAL = "manual", "Qo'lda"
    AUTO_CREATOR = "auto_creator", "Avto (yaratuvchi)"
    AUTO_ASSIGNEE = "auto_assignee", "Avto (biriktirilgan)"
    BACKFILL = "backfill", "Migratsiya"
```

`ROLE_RANK` o'zgarmaydi.

### B.2 `Workspace` ga qo'shiladigan maydon

```python
permissions_version = models.PositiveIntegerField(default=1, editable=False)
```
Matritsa har o'zgarganda `F("permissions_version") + 1`. Serializerda read-only.

### B.3 `RolePermission` — `apps/workspaces/models.py`

```python
class RolePermission(UUIDModel, TimeStampedModel):
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="role_permissions"
    )
    role = models.CharField(max_length=10, choices=AssignableRole.choices, db_index=True)
    permission = models.CharField(max_length=64, db_index=True)   # katalog kodi
    allowed = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "workspace_role_permissions"
        ordering = ["role", "permission"]
        verbose_name = "rol ruxsati"
        verbose_name_plural = "rol ruxsatlari"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "role", "permission"],
                name="uniq_role_permission_per_workspace",
            ),
            models.CheckConstraint(
                condition=~models.Q(role="owner"), name="role_permission_never_owner"
            ),
        ]
        indexes = [models.Index(fields=["workspace", "role"], name="idx_roleperm_ws_role")]

    def clean(self):
        from apps.core.permissions import PERMISSION_BY_CODE
        definition = PERMISSION_BY_CODE.get(self.permission)
        if definition is None:
            raise ValidationError({"permission": "Noma'lum ruxsat kodi."})
        if definition.owner_only and self.allowed:
            raise ValidationError({"permission": "Bu ruxsat faqat owner uchun."})
```

`permission` — `CharField`, FK emas (AD-1). Bir workspace uchun to'liq matritsa = 3 rol × butun katalog (v5: 49 kod) = **147 qator**.

### B.4 `SpaceMember` — `apps/workspaces/models.py`

```python
class SpaceMember(UUIDModel, TimeStampedModel):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="space_members")
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="space_memberships"
    )
    access = models.CharField(
        max_length=12, choices=SpaceAccess.choices,
        default=SpaceAccess.CONTRIBUTOR, db_index=True,
    )
    source = models.CharField(
        max_length=14, choices=SpaceMemberSource.choices, default=SpaceMemberSource.MANUAL
    )
    added_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "space_members"
        ordering = ["access", "user__email"]
        verbose_name = "bo'lim a'zosi"
        verbose_name_plural = "bo'lim a'zolari"
        constraints = [
            models.UniqueConstraint(fields=["space", "user"], name="uniq_space_member")
        ]
        indexes = [
            models.Index(fields=["user", "space"], name="idx_spacemember_user_space"),
            models.Index(fields=["space", "access"], name="idx_spacemember_space_access"),
        ]
```

**Invariant:** `SpaceMember.user` shu space'ning workspace'ida `WorkspaceMember` bo'lishi shart (servis qatlamida tekshiriladi). `_remove_member()` workspace'dan chiqarishda space qatorlarini ham o'chiradi.

### B.5 Visibility qoidalari (BINDING)

Space `S` chaqiruvchi `m` uchun **ko'rinadi**, agar:

```
m.role == owner
  OR has_perm(m, "space.read_private")            # default: admin
  OR (S.is_private == False AND has_perm(m, "space.read"))
  OR SpaceMember.objects.filter(space=S, user=m.user).exists()
```
Ko'rinmasa → **`404 not_found`** (mavjudlik oshkor qilinmaydi).

Space ichidagi yozish:
- `access == viewer` → space ichidagi barcha yozish `403` (**eng past huquq g'olib**).
- `access == contributor` → workspace roli bo'yicha odatiy `has_perm`.
- `access == manager` (PM) → contributor + shu space uchun `space.update`, `space.manage_members`, `space.manage_statuses`, `folder.*`, `list.*`, `task.*` lokal yoqiladi.
- `space.delete` va `space.change_visibility` **hech qachon** manager orqali berilmaydi: PM bo'lim **ichida** hokim, bo'limning ish maydoniga nisbatan **chegarasini** o'zgartira olmaydi.

### B.6 Defaultlar qanday to'ldiriladi

```python
# apps/workspaces/services.py
def ensure_role_permissions(workspace) -> int:
    """Idempotent: yetishmayotgan (role, permission) qatorlarini defaultdan yaratadi."""
    from apps.core.permissions import PERMISSIONS
    existing = set(
        RolePermission.objects.filter(workspace=workspace).values_list("role", "permission")
    )
    rows = [
        RolePermission(
            workspace=workspace, role=role, permission=p.code, allowed=(role in p.defaults)
        )
        for p in PERMISSIONS if not p.deprecated
        for role in AssignableRole.values
        if (role, p.code) not in existing
    ]
    RolePermission.objects.bulk_create(rows, ignore_conflicts=True)
    return len(rows)
```

Uch nuqta: (1) migratsiya `0003`, (2) `bootstrap_workspace()`, (3) resolver fallback. `create_space()` yaratuvchi uchun `SpaceMember(access=manager, source=auto_creator)` yaratadi.

### B.7 Legacy → permission ko'chirish jadvali

`ROLE_RANK` faqat 4 joyda qoladi: `ROSTER_RANK`, monotonlik validatsiyasi, `MemberDetailView` rank guard, `_owner_count()` invariantlari. `require_role` shim sifatida qoladi (`DeprecationWarning`).

| Fayl · view | Hozir | Yangi |
|---|---|---|
| `workspaces` `WorkspaceDetailView.patch` | `owner` | `workspace.update` |
| `workspaces` `WorkspaceDetailView.delete` | `owner` | `workspace.delete` |
| `workspaces` `MemberListView.get` | `member` | `member.read` |
| `workspaces` `MemberDetailView.patch` | `admin` | `member.role_change` (+ rank guard) |
| `workspaces` `MemberDetailView.delete` | `admin` | `member.remove` (+ rank guard) |
| `workspaces` `InvitationListCreateView.get` | `admin` | `invitation.read` |
| `workspaces` `InvitationListCreateView.post` | `admin` | `member.invite` |
| `workspaces` `_get_invitation_for_admin` | `admin` | `invitation.manage` |
| `workspaces` `SpaceListCreateView.post` | `admin` | `space.create` |
| `workspaces` `SpaceDetailView.patch` | `admin` | `space.update` |
| `workspaces` `SpaceDetailView.delete` | `admin` | `space.delete` |
| `workspaces` `FolderListCreateView.post` | `member` | `folder.create` |
| `workspaces` `FolderDetailView.patch` | `member` | `folder.update` |
| `workspaces` `FolderDetailView.delete` | `admin`/`member` | `folder.delete_cascade` / `folder.delete` |
| `workspaces` `ListListCreateView.post` | `member` | `list.create` |
| `workspaces` `ListDetailView.patch` | `member` | `list.update` |
| `workspaces` `ListDetailView.delete` | `member` | `list.delete` |
| `workspaces` `ListMoveView.patch` | `member` | `list.move` |
| `workspaces` `SpaceStatusSetView.put` | `admin` | `space.manage_statuses` |
| `workspaces` `ListStatusSetView.put/delete` | `admin` | `list.manage_statuses` |
| `tasks` `ListTasksView.post` | `member` | `task.create` |
| `tasks` `require_task_editor` | rol | `task.update` → `task.update_assigned` |
| `tasks` `TaskDetailView.delete` | `member` | `task.delete` |
| `tasks` `TaskDetailView._restore` | `admin` | `task.restore` |
| `tasks` `TaskMoveView.patch` | editor | `task.move` → `task.update_assigned` |
| `tasks` `WorkspaceTagsView.post` | `member` | `tag.create` |
| `tasks` `TagDetailView.patch/delete` | `member` | `tag.update` / `tag.delete` |
| `tasks/filters.py` `include_deleted_requested` | `admin` | `task.view_deleted` |
| `comments` `TaskCommentsView.post` | implicit | `comment.create` |
| `comments` `CommentDetailView.patch` | author | `comment.update_own` + author check |
| `comments` `CommentDetailView.delete` | author/admin | `comment.delete_own` / `comment.delete_any` |

**Merge gate:** `DEFAULT_MATRIX` bu jadvalga aynan mos → mavjud testlar **kod o'zgarishisiz** o'tishi shart.

---

## C. Access layer — `apps/core/access.py`

### C.1 Public API
```python
def has_perm(membership, code: str) -> bool: ...
def require_perm(membership, code: str): ...              # 403
def require_membership_perm(user, workspace_id, code): ... # 404 keyin 403
def has_space_perm(membership, space, code: str) -> bool: ...
def require_space_perm(membership, space, code: str): ...
def effective_permissions(workspace) -> dict[str, frozenset[str]]: ...
def my_permissions(membership) -> frozenset[str]: ...
```
`get_membership`, `require_membership`, `check_space_visible`, `visible_spaces_q` — imzolari saqlanadi.

### C.2 `has_perm`
```python
def has_perm(membership, code):
    from apps.core.permissions import PERMISSION_BY_CODE
    if settings.DEBUG and code not in PERMISSION_BY_CODE:
        raise ImproperlyConfigured(f"Noma'lum ruxsat kodi: {code}")
    if membership.role == WorkspaceRole.OWNER:
        return True                                   # AD-3
    cached = getattr(membership, "_perm_set", None)
    if cached is None:
        cached = effective_permissions(membership.workspace).get(membership.role, frozenset())
        membership._perm_set = cached
    return code in cached
```

### C.3 Caching — uch qavat
```python
PERMISSION_CACHE_TTL = 300

def _cache_key(workspace):
    return f"wsperm:{workspace.id}:{workspace.permissions_version}"

def _build_matrix(workspace):
    from apps.core.permissions import DEFAULT_MATRIX, PERMISSION_BY_CODE
    matrix = {r: set(DEFAULT_MATRIX[r]) for r in AssignableRole.values}
    rows = RolePermission.objects.filter(workspace_id=workspace.id).values_list(
        "role", "permission", "allowed"
    )
    for role, code, allowed in rows:
        if code not in PERMISSION_BY_CODE or role not in matrix:
            continue
        (matrix[role].add if allowed else matrix[role].discard)(code)
    return {r: frozenset(v) for r, v in matrix.items()}
```

| Qavat | Umr | Maqsad |
|---|---|---|
| `membership._perm_set` | bitta view chaqiruvi | Loop ichidagi takroriy `has_perm` |
| `_REQUEST_LOCAL` (contextvar dict) | bitta HTTP request | Ko'p membership obyekti |
| Django `cache` | 300 s yoki version bump | Process bo'ylab |

Cache hit → **+0 query**. `assertNumQueries` testi ≤6 query byudjetini qulflaydi.

**Invalidatsiya:**
```python
@transaction.atomic
def bump_permissions_version(workspace, *, actor=None):
    Workspace.objects.filter(pk=workspace.pk).update(
        permissions_version=F("permissions_version") + 1, updated_at=timezone.now()
    )
    workspace.refresh_from_db(fields=["permissions_version"])
    transaction.on_commit(lambda: events.emit_permissions_updated(workspace, actor=actor))
```
Version kalitda bo'lgani uchun eski kalit hech qachon o'qilmaydi → **bir zumda, cross-process**.

### C.4 404 vs 403 tartibi (qat'iy)
```
1. Resurs mavjudmi?         yo'q → 404
2. require_membership       a'zo emas → 404
3. check_space_visible      ko'rinmaydi → 404   ← SpaceMember shu yerda
4. require_perm             ruxsat yo'q → 403
5. serializer.is_valid()    → 400
```

### C.5 `visible_spaces_q`
```python
def visible_spaces_q(membership):
    if membership.role == WorkspaceRole.OWNER or has_perm(membership, "space.read_private"):
        return Q()
    explicit = Q(space_members__user_id=membership.user_id)
    if has_perm(membership, "space.read"):
        return Q(is_private=False) | explicit
    return explicit
```

> ⚠️ **Tuzatilishi shart:** `apps/tasks/views.py::WorkspaceTasksView.get` hozir `visible_spaces_q` ni chaqirmasdan o'z mantiqini takrorlaydi → yangi qoidada **yopiq bo'lim vazifalarini oqizadi**. Bitta helperga keltirilishi shart: `WorkspaceTreeView`, `SpaceListCreateView`, `WorkspaceSearchView`, `WorkspaceTasksView`, `apps/realtime/consumers.py::_list_access`.

---

## D. API kontrakti o'zgarishlari

Barchasi `/api/v1/` ostida, trailing slash bilan, xato formati `{"error":{"code","message","details"}}`.

### D.1 `GET permissions/` — katalog
Auth required, rol talab qilinmaydi, **pagination yo'q**.
```json
{
  "catalog_version": 5,
  "groups": [{
    "key": "task", "label": "Vazifalar",
    "permissions": [{
      "code": "task.delete", "label": "Vazifani o'chirish",
      "description": "Vazifani soft-delete qiladi; 30 kun ichida tiklash mumkin.",
      "default_roles": ["admin"], "owner_only": false, "sensitive": false
    }]
  }]
}
```
`default_roles` `owner` ni **o'z ichiga olmaydi**.

### D.2 `GET workspaces/{id}/role-permissions/`
Ruxsat: `workspace.manage_permissions` (default: faqat owner).
```json
{
  "workspace_id": "…", "version": 7, "catalog_version": 5,
  "roles": {
    "owner":  { "locked": true,  "permissions": ["…barcha 49 kod…"] },
    "admin":  { "locked": false, "permissions": ["…"] },
    "member": { "locked": false, "permissions": ["…"] },
    "guest":  { "locked": false, "permissions": ["…"] }
  },
  "overrides": [
    { "role": "member", "permission": "space.create", "allowed": true,
      "updated_by_id": "…", "updated_at": "2026-08-10T11:00:00Z" }
  ]
}
```
`permissions` alifbo tartibida. `overrides` — defaultdan farq qiluvchilar (UI "o'zgartirilgan" belgisi).
Xatolar: `401`, `403`, `404`.

### D.3 `PUT workspaces/{id}/role-permissions/`
```json
{ "expected_version": 7,
  "roles": { "member": { "space.create": true, "task.delete": false },
             "guest":  { "comment.create": false } } }
```
**200:** `GET` bilan bir xil, `version` = 8.

| HTTP | `code` | Qachon | `details` |
|---|---|---|---|
| 400 | `validation_error` | Noma'lum kod | `{"roles.member.foo_bar": ["Noma'lum ruxsat kodi."]}` |
| 400 | `validation_error` | `owner` roliga yozish | `{"roles.owner": ["Owner ruxsatlarini o'zgartirib bo'lmaydi."]}` |
| 400 | `validation_error` | `owner_only` kodni grant | `{"roles.admin.workspace.manage_permissions": ["Bu ruxsat faqat owner uchun."]}` |
| 400 | `validation_error` | Monotonlik buzilishi | `{"monotonic": ["'space.create' member'da yoqilgan, admin'da o'chirilgan."]}` |
| 403 | `permission_denied` | Ruxsat yo'q | `{}` |
| 403 | `permission_denied` | O'z roli yoki undan yuqorini o'zgartirish | `{"reason": "self_escalation", "role": "admin"}` |
| 409 | `conflict` | `expected_version` mos emas | `{"expected_version": 7, "current_version": 9}` |

`expected_version` **majburiy** (optimistic concurrency). Yon ta'sir: `permissions_version += 1`, WS `permission.updated`.

### D.4 `POST workspaces/{id}/role-permissions/reset/`
Body: `{"role": "member"}` yoki `{"role": null}` (barchasi). 200 → `GET` shakli.

### D.5 `GET workspaces/{id}/my-permissions/`
Ruxsat: **har qanday a'zo** (guest ham).
```json
{ "workspace_id": "…", "role": "member", "version": 7,
  "permissions": ["comment.create", "list.create", "task.create", "…"],
  "spaces": [{ "space_id": "…", "access": "manager" }] }
```
Frontend butun UI gating'ini shu bitta so'rovdan quradi.

### D.6 Space a'zolari (PM biriktiruvi)

| Method | Path | Ruxsat | Success |
|---|---|---|---|
| GET | `spaces/{id}/members/` | space ko'rinadigan a'zo | `200` paginated |
| POST | `spaces/{id}/members/` | `space.manage_members` yoki lokal `manager` | `201` |
| PATCH | `spaces/{id}/members/{user_id}/` | bir xil | `200` |
| DELETE | `spaces/{id}/members/{user_id}/` | bir xil | `204` |
| POST | `spaces/{id}/members/bulk/` | bir xil | `200` |

```json
{ "id": "…", "space_id": "…",
  "user": { "id": "…", "email": "dan@acme.io", "full_name": "Dan Ortiz",
            "avatar": null, "avatar_color": "#49CCF9" },
  "access": "contributor", "source": "manual", "added_by_id": "…",
  "created_at": "…", "updated_at": "…" }
```
POST body: `{"user_id": "…", "access": "viewer"|"contributor"|"manager"}`
Bulk body: `{"add": [{"user_id": "…", "access": "contributor"}], "remove": ["…uuid…"]}` — bitta tranzaksiya, qisman muvaffaqiyat yo'q.

| HTTP | `code` | Qachon |
|---|---|---|
| 400 | `validation_error` | `user_id` workspace a'zosi emas |
| 403 | `permission_denied` | Ruxsat yo'q |
| 404 | `not_found` | Space ko'rinmaydi / user a'zo emas |
| 409 | `conflict` | Takroriy `(space, user)` |
| 409 | `conflict` | Yopiq space'ning oxirgi `manager`ini olib tashlash → `{"reason": "last_manager"}` |

### D.7 `GET invitations/lookup/?token=` — kengaytirilgan (public)
```json
{ "workspace_id": "…", "workspace_name": "Acme Inc.", "workspace_color": "#7B68EE",
  "email": "carlos@client.com", "role": "guest",
  "invited_by": { "full_name": "Maya Chen", "email": "maya@acme.io",
                  "avatar": null, "avatar_color": "#7B68EE" },
  "account_exists": false, "expires_at": "2026-08-14T09:15:00Z" }
```
`invited_by` **`id` maydonisiz** (public endpoint). **YANGI throttle:** `invite_lookup` scope **30/min per IP**. Noma'lum/muddati o'tgan/bekor → `404`.

### D.8 `POST auth/register/` — invite-token bilan
```json
{ "email": "carlos@client.com", "password": "S3cure!passw0rd",
  "full_name": "Carlos Vega", "invite_token": "hR3k…", "workspace_name": null }
```
**Qoidalar (BINDING):**
1. `invite_token` + `workspace_name` birga → `400`, `details.workspace_name`.
2. Token noto'g'ri/muddati o'tgan/`pending` emas → **`404`** (`403` EMAS).
3. `email` taklif emailiga CI teng bo'lmasa → `400`, `details.email`.
4. Bitta `transaction.atomic()`: User → Invitation `accepted` → `WorkspaceMember(role=invitation.role, invited_by=…)` → `refresh_member_count()`.
5. Race: `Invitation` `SELECT … FOR UPDATE`. Ikkinchi urinish → `409`.
6. `full_name` — `invite_token` bo'lganda majburiy (min 2 belgi).

**201:** `{access, refresh, user, workspace_id}` — `workspace_id` yangi ixtiyoriy maydon.

**Kuchaytirilgan validatsiya (barcha register uchun):**

| Maydon | Qoida |
|---|---|
| `email` | EmailField, lowercase, CI-unique, max 254 |
| `password` | Django validators + **min 10 belgi** |
| `full_name` | trim, 2–150, `<`/`>`/URL naqshi taqiqlanadi |
| `workspace_name` | trim, 2–120 |
| `invite_token` | 1–64, `[A-Za-z0-9_-]+` |

**Throttle:** yangi `register` scope **10/min per IP**; `.env.example` ga `REGISTER_THROTTLE_RATE=10/min`.

### D.9 Xato kodlari — yangi kod qo'shilmaydi
Mavjud yopiq to'plam: `validation_error`, `permission_denied`, `not_found`, `conflict`, `throttled`. `details` ichida `reason` kaliti (`"self_escalation"`, `"last_manager"`, `"monotonic"`).

### D.10 WebSocket kengaytmasi

| `type` | Kanal | `data` | Klient |
|---|---|---|---|
| `permission.updated` | workspace | `{"workspace_id": "…", "version": 8}` | `my-permissions` va `role-permissions` invalidate |
| `access.revoked` | `user.<id>` | `{"workspace_id": "…", "space_id": "…\|null"}` | Invalidate; ko'rayotgan bo'lsa `/w/{id}` ga |

### D.11 Kontrakt rulinglari (§17)

| # | Ruling |
|---|---|
| R18 | §1.7 statik rol jadvali → matritsa g'olib; §1.7 endi **default**ni tavsiflaydi. |
| R19 | DATA_MODEL D8 bekor qilinadi: `SpaceMember` joriy etiladi; `is_private` "ACL majburiy" flagi. |
| R20 | Yopiq bo'lim faqat `space.read_private` yoki `SpaceMember` orqali ko'rinadi; migratsiya backfill qiladi. |
| R21 | Register javobiga `workspace_id` ixtiyoriy maydon qo'shildi. |
| R22 | `lookup/` kengaytirildi; `id` maydonlari oshkor qilinmaydi. |
| R23 | WS yopiq to'plamiga `permission.updated`, `access.revoked` qo'shildi. |

Endpoint inventari: 64 → **71**.

---

## E. Frontend shartnomasi — `frontend/src/types/api.ts`

```ts
export type PermissionCode =
  | "workspace.read" | "workspace.update" | "workspace.delete"
  | "workspace.manage_permissions" | "workspace.transfer_ownership"
  | "member.read" | "member.invite" | "member.remove" | "member.role_change"
  | "invitation.read" | "invitation.manage"
  | "space.read" | "space.read_private" | "space.create" | "space.update"
  | "space.delete" | "space.manage_members" | "space.manage_statuses"
  | "folder.create" | "folder.update" | "folder.delete" | "folder.delete_cascade"
  | "list.create" | "list.update" | "list.delete" | "list.move" | "list.manage_statuses"
  | "task.read" | "task.create" | "task.update" | "task.update_assigned"
  | "task.delete" | "task.move" | "task.assign" | "task.watch"
  | "task.restore" | "task.view_deleted"
  | "comment.create" | "comment.update_own" | "comment.delete_own" | "comment.delete_any"
  | "tag.create" | "tag.update" | "tag.delete";

export type PermissionGroupKey =
  | "workspace" | "member" | "space" | "folder" | "list" | "task" | "comment" | "tag";

export type AssignableRole = Exclude<Role, "owner">;

export interface PermissionDef {
  code: PermissionCode;
  label: string;
  description: string;
  default_roles: AssignableRole[];   // owner HECH QACHON bu yerda emas
  owner_only: boolean;
  sensitive: boolean;
}

export interface PermissionGroup {
  key: PermissionGroupKey;
  label: string;
  permissions: PermissionDef[];
}

export interface PermissionCatalog {
  catalog_version: number;
  groups: PermissionGroup[];
}

export interface RolePermissionRow {
  role: AssignableRole;
  permission: PermissionCode;
  allowed: boolean;
  updated_by_id: string | null;
  updated_at: string;
}

export interface RolePermissionMatrix {
  workspace_id: string;
  version: number;                   // optimistic concurrency tokeni
  catalog_version: number;
  roles: Record<Role, { locked: boolean; permissions: PermissionCode[] }>;
  overrides: RolePermissionRow[];
}

export interface UpdateRolePermissionsRequest {
  expected_version: number;
  roles: Partial<Record<AssignableRole, Partial<Record<PermissionCode, boolean>>>>;
}

export interface ResetRolePermissionsRequest { role: AssignableRole | null; }

export interface MyPermissions {
  workspace_id: string;
  role: Role;
  version: number;
  permissions: PermissionCode[];
  spaces: { space_id: string; access: SpaceAccess }[];
}

export type SpaceAccess = "viewer" | "contributor" | "manager";
export type SpaceMemberSource = "manual" | "auto_creator" | "auto_assignee" | "backfill";

export interface SpaceMember {
  id: string;
  space_id: string;
  user: UserSummary;
  access: SpaceAccess;
  source: SpaceMemberSource;
  added_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AddSpaceMemberRequest { user_id: string; access: SpaceAccess; }
export interface BulkSpaceMembersRequest { add: AddSpaceMemberRequest[]; remove: string[]; }
export interface BulkSpaceMembersResponse { added: number; removed: number; results: SpaceMember[]; }

export interface InvitationLookup {
  workspace_id: string;
  workspace_name: string;
  workspace_color: string;
  email: string;
  role: InvitableRole;
  invited_by: Pick<UserSummary, "full_name" | "email" | "avatar" | "avatar_color">;
  account_exists: boolean;
  expires_at: string;
}
```

**Mavjud tiplarga qo'shimchalar:** `Workspace.permissions_version: number`; `RegisterRequest.invite_token?: string`; `AuthResponse.workspace_id?: string | null`; `WsEventType` ga `"permission.updated" | "access.revoked"`.

### E.1 `frontend/src/lib/roles.ts`
```ts
export const SPACE_ACCESS_LABEL: Record<SpaceAccess, string> = {
  viewer: "Ko'ruvchi", contributor: "Ishtirokchi", manager: "Menejer (PM)",
};
export const PERMISSION_GROUP_LABEL: Record<PermissionGroupKey, string> = {
  workspace: "Ish maydoni", member: "A'zolar", space: "Bo'limlar", folder: "Jildlar",
  list: "Ro'yxatlar", task: "Vazifalar", comment: "Izohlar", tag: "Teglar",
};
```

### E.2 Hook'lar
`keys.ts`: `permissionCatalog`, `myPermissions(wid)`, `rolePermissions(wid)`, `spaceMembers(sid)`, `invitationLookup(token)`.
`queries.ts`: `usePermissionCatalog()` (staleTime `Infinity`), `useMyPermissions(wid)` (5 min), `useRolePermissions(wid, canRead)`, `useSpaceMembers(sid)`, `useInvitationLookup(token)` (public — `api` ga `auth:false` opsiyasi kerak).
`mutations.ts`: `useUpdateRolePermissions(wid)` (409 → "Boshqa admin matritsani o'zgartirdi" + invalidate), `useResetRolePermissions(wid)`, `useAddSpaceMember(sid)`, `useBulkSpaceMembers(sid)`, `useRemoveSpaceMember(sid)`.

`frontend/src/lib/permissions.ts`:
```ts
export function can(my: MyPermissions | undefined, code: PermissionCode): boolean {
  if (!my) return false;
  if (my.role === "owner") return true;
  return my.permissions.includes(code);
}
export function canInSpace(
  my: MyPermissions | undefined, spaceId: string, code: PermissionCode
): boolean { /* manager lokal yoqishlarini hisobga oladi */ }
```
**`can()` faqat UI affordance uchun. Server har doim mustaqil tekshiradi.**

### E.3 Yangi sahifalar

| Marshrut | Mazmun |
|---|---|
| `/w/[workspaceId]/settings/permissions` | Matritsa: qatorlar = kodlar (guruhlangan, collapsible), ustunlar = 4 rol. `owner` ustuni disabled + qulf ikonkasi. Diff-badge. "Saqlash" `expected_version` bilan. |
| `/w/[workspaceId]/settings/members` | Mavjud roster kengaytiriladi |
| `/w/[workspaceId]/s/[spaceId]/members` | PM paneli: chapda workspace roster, o'ngda space a'zolari, `access` select, bulk save |
| `/invite/[token]` | Public: `lookup` → `account_exists` bo'yicha `/login?next=…` yoki `/register?token=…` |
| `/register?token=…` | Email oldindan to'ldirilgan va `readOnly`, workspace nomi yashiriladi, banner: "Siz «Acme Inc.» ish maydoniga *A'zo* sifatida taklif qilingansiz" |

---

## F. Xavfsizlik tahlili

**F-1 · Admin o'z rolini oshirishi.** Uch qavat: (1) `workspace.manage_permissions` default'da faqat owner'da; (2) **rank guard** — `ROLE_RANK[target_role] >= ROLE_RANK[caller.role]` → `403` + `details.reason="self_escalation"`; (3) `owner_only` kodlar hech qachon grant qilinmaydi → `400`.

**F-2 · Oxirgi owner.** Invariantlar permission tizimidan **tashqarida**, `_owner_count()` bilan `409`. Qoida: *permission matritsasi qaysi amal mumkinligini, `ROLE_RANK` kim-kimga-nisbatan qoidasini boshqaradi. Ikkalasi ham o'tishi shart.*

**F-3 · Guest yopiq space'ni ko'rishi.** Yopilishi kerak bo'lgan yo'llar: `spaces/`, `tree/`, `search/`, **`tasks/` (⚠️ hozir o'z mantiqini takrorlaydi)**, `spaces/{id}/`, `folders/`, `lists/`, `tasks/{id}/`, **WS `ws/list/{id}/`**, `comments/`, `move/` destination, cross-space `assignee_ids`. CI gate: `test_private_space_invisible_from_every_endpoint` (parametrized ×8).

**F-4 · Stale grant.** Cache kaliti `permissions_version` ni o'z ichiga oladi va version har request'da DB'dan o'qiladi → **bekor qilish bir zumda**. Qolgan xavf: ochiq WS soketlari → `access.revoked` / `permission.updated` frame'lari.

**F-5 · Space manager (PM) eskalatsiyasi.** `manager` lokal yoqishlari qat'iy `SPACE_MANAGER_GRANTS` frozenset bilan cheklangan. `space.delete`, **`space.change_visibility`**, `member.*`, `workspace.*`, `tag.*` **hech qachon** kirmaydi. `viewer` bo'lsa hammasi kesiladi. CI: `apps/core/tests/test_security_followups.py::test_change_visibility_is_admin_only_and_never_local_to_a_manager`.

**F-6 · Invite token brute-force.** `lookup/` public va **throttlesiz** — register-with-invite bu yo'lni kengaytiradi. Majburiy: `invite_lookup` 30/min per IP; register xatosi ham `register` throttle'iga kiradi. Token entropiyasi `token_urlsafe(32)` = 256 bit — yetarli. Keyingi sprint: `token_hash` (sha256) + `token_prefix`.

**F-7 · Django `/admin/` orqali chetlab o'tish.** `CheckConstraint(role != 'owner')`; `RolePermissionAdmin` add/change/delete → **faqat `is_superuser`**; `save_model`/`delete_model`/`save_formset` → `bump_permissions_version()`.

**F-8 · Mass assignment.** `PUT role-permissions/` payload'i `PERMISSION_BY_CODE` va `AssignableRole.values` bo'yicha **whitelist**. Noma'lum kalit → `400` (silent ignore EMAS).

**F-9 · Monotonlik** `PUT` da, `clean()` da va admin formda tekshiriladi.

**F-10 · Chiqarilgan a'zoning ochiq WebSocket'i.** Consumer a'zolikni faqat `connect()` da bir marta tekshiradi, shuning uchun `_remove_member()` (`members/{id}/` DELETE va `members/leave/`) `transaction.on_commit` ichida `emit_access_revoked(user_id, workspace_id=…, space_id=None)` chiqaradi. `space_id=None` `revocation_applies()` bo'yicha **ikkala** consumer'ni ham (ro'yxat va ish maydoni) `4403` bilan yopadi. `user_id` `membership.delete()` dan **oldin** olinadi.

**F-11 · `assignee_ids` orqali `task.assign` ni chetlab o'tish.** `POST lists/{id}/tasks/` va `PATCH tasks/{id}/` biriktirishlar to'plami **chaqiruvchidan boshqa odam uchun o'zgarganda** qo'shimcha `require_space_perm(…, "task.assign")` talab qiladi. Ikki holat ataylab tekshirilmaydi: (1) to'plam umuman o'zgarmagan (frontend to'liq obyektni qaytarib yuboradi), (2) farq faqat chaqiruvchining o'zi — "vazifani olaman" / "tashlab ketaman" oqimlari admin aralashuvisiz ishlashi kerak va ular hech kimga yangi kirish bermaydi (chaqiruvchi bo'limni allaqachon ko'rmoqda, `_grant_assignee_space_access` esa ko'rayotgan odamga qator yozmaydi). Ikkinchi qavat: `_grant_assignee_space_access()` `SpaceMember` qatorini faqat aktyor `space.manage_members` ga ega bo'lganda yozadi, aks holda `400 validation_error` (`details.assignee_ids`). Aks holda `space.manage_members` (admin-only) `task.update_assigned` (guest-level) orqali aylanib o'tilardi.

---

## G. Migratsiya va rollout

### G.1 Migratsiyalar
```
workspaces.0002_permissions_and_space_members   ← schema
workspaces.0003_seed_role_permissions           ← data
workspaces.0004_backfill_space_members          ← data
```

**0002** (atomic): `AddField Workspace.permissions_version`; `CreateModel RolePermission`; `CreateModel SpaceMember`.

**0003** — katalog snapshot'i migratsiya faylining **ichida** literal dict sifatida; `apps.core.permissions` dan **import qilinmaydi** (katalog evolyutsiya qiladi, migratsiya tarixiy holatni takrorlaydi). `bulk_create(..., ignore_conflicts=True)` → idempotent.

**0004** — hech kim kirishni yo'qotmasligi uchun backfill:
- Yopiq space: barcha non-guest workspace a'zolari → `owner`/`admin` = `manager`, boshqalar = `contributor`, `source="backfill"`.
- Ochiq space: faqat `created_by` → `manager`, `source="auto_creator"`.
- Yopiq space'da vazifasi bor guestlar → `viewer`, `source="auto_assignee"`.

**Kafolat:** `test_backfill_preserves_visibility` — migratsiyadan oldingi/keyingi visibility matritsasi taqqoslanadi, **merge gate**.

**`db.sqlite3` xavfsizligi:** uchala migratsiya ham **additive** (ustun o'chirilmaydi, `ALTER COLUMN` yo'q). Rollback: `migrate workspaces 0001`. **Deploy oldidan `db.sqlite3` nusxasini oling.**

### G.2 Rollout fazalari

| Faza | Ish | Xatti-harakat o'zgaradimi | Rollback |
|---|---|---|---|
| 0 | Katalog + `test_default_matrix_matches_legacy_roles` | yo'q | — |
| 1 | Migratsiya 0002–0004, `ensure_role_permissions`, admin | yo'q | `migrate workspaces 0001` |
| 2 | `has_perm`/`require_perm`/cache; `require_role` shim | yo'q | git revert |
| 3 | View'larni §B.7 bo'yicha ko'chirish (app-app, har PR'da `pytest` yashil) | yo'q | git revert |
| 4 | `visible_spaces_q` yangi qoidasi + `WorkspaceTasksView`/`_list_access` tuzatish | **HA** (R20) | `SPACE_ACL_ENABLED` env flag |
| 5 | Yangi endpoint'lar + WS event'lar | additive | URL'larni olib tashlash |
| 6 | `lookup/` kengaytmasi + throttle + `invite_token` | additive | — |
| 7 | Django admin kuchaytirish | faqat staff | — |
| 8 | Frontend: tiplar → hooks → sahifalar → gating | UI | — |
| 9 | `API_CONTRACT.md` v1.1.0 + `DATA_MODEL.md` (**bir commitda**) | hujjat | — |

### G.3 Django `/admin/` spetsifikatsiyasi

```
WorkspaceAdmin
  list_display = (name, slug, owner, member_count, permissions_version, created_at)
  list_select_related = ("owner",);  search_fields = (name, slug, owner__email)
  readonly_fields = (slug, member_count, permissions_version, created_at, updated_at)
  inlines = [WorkspaceMemberInline, RolePermissionInline]
  actions = ["reset_permission_matrix", "ensure_permission_rows"]

WorkspaceMemberInline (TabularInline)  extra=0, autocomplete_fields=("user",)
RolePermissionInline  (TabularInline)  extra=0, can_delete=False,
  readonly_fields=(role, permission, updated_by)   # faqat `allowed` tahrirlanadi
  has_add_permission -> False;  classes=["collapse"]   # 132 qator — default yopiq

RolePermissionAdmin (mustaqil)
  list_display = (workspace, role, permission, allowed, updated_by, updated_at)
  list_filter = (role, allowed, PermissionGroupFilter);  list_editable = ("allowed",)
  search_fields = (workspace__name, permission);  autocomplete_fields = ("workspace",)
  actions = ["grant_selected", "revoke_selected", "reset_to_default"]
  has_add/change/delete_permission -> request.user.is_superuser
  save_model/delete_model/save_formset -> bump_permissions_version(workspace)

SpaceAdmin      inlines=[SpaceMemberInline]; list_filter=(is_private, archived, workspace)
                actions=["make_private","make_public","sync_creator_as_manager"]
SpaceMemberAdmin  list_display=(space,user,access,source,created_at); list_filter=(access,source)
InvitationAdmin   += (invited_by, sent_count, last_sent_at, is_expired_display)
                  readonly_fields=("token",);  has_add_permission -> False
                  actions=["revoke_selected","extend_expiry_7d"]

UserAdmin  ← django.contrib.auth.admin.UserAdmin dan meros (ModelAdmin EMAS)
  search_fields=(email, full_name)   # autocomplete_fields uchun MAJBURIY
  inlines=[WorkspaceMembershipInline] (read-only)
  actions=["deactivate_users","activate_users"]
```
`admin.site.site_header = "Clickish boshqaruvi"`, `site_title`, `index_title` — o'zbekcha.

> ⚠️ **Bug (TUZATILDI 2026-08-10):** `apps/accounts/admin.py` `admin.ModelAdmin` dan meros olardi → admin orqali saqlanganda parol **plaintext** yozilardi. Endi `BaseUserAdmin`.

---

## H. Risklar va trade-off'lar

| # | Risk | Eht. | Ta'sir | Tavsiya |
|---|---|---|---|---|
| R1 | Space visibility o'zgarishi (R20) mavjud foydalanuvchilarni bloklashi | o'rta | yuqori | `0004` backfill barcha non-guest a'zolarni yozadi (nol yo'qotish); Faza 4 `SPACE_ACL_ENABLED` flag ostida; `test_backfill_preserves_visibility` merge gate |
| R2 | Monotonlik (AD-5) real ssenariylarni bloklashi | o'rta | o'rta | Cheklovni **saqlash**. Talab paydo bo'lsa javob — yangi rol yoki `SpaceMember.access`, rolni bo'shashtirish emas. Hujjatda "bilib qabul qilingan cheklov" deb yozilsin |
| R3 | Cache invalidatsiyasi noto'g'ri → jimgina xavfsizlik teshigi | past | juda yuqori | `bump_permissions_version()` — `RolePermission` yozadigan **yagona** yo'l; `post_save`/`post_delete` signal safety net; `test_permission_revocation_is_immediate`; pytest'da har test orasida `cache.clear()` |
| R4 | +2 round-trip frontend'ni sekinlashtiradi | yuqori | past | Katalog `staleTime: Infinity` + `localStorage`; `my-permissions` 5 min + WS invalidatsiya. `my_permissions` ni `Workspace` obyektiga **kiritmang** |
| R5 | Katalog ↔ view drift (kod bor, hech kim tekshirmaydi) | yuqori | o'rta | `test_every_permission_code_is_enforced_somewhere` (AST skaner); `test_no_legacy_require_role_in_views` (whitelist bilan) |

---

## I. Testlash majburiyatlari (merge gate)

| Test | Fayl | Nima isbotlaydi |
|---|---|---|
| `test_default_matrix_matches_legacy_roles` | `apps/core/tests/` | AD-9 — regressiya yo'q |
| `test_default_matrix_is_monotonic` | `apps/core/tests/` | AD-5 |
| `test_owner_always_has_every_permission` | `apps/core/tests/` | AD-3 |
| `test_permission_query_budget` (`assertNumQueries`) | `apps/tasks/tests.py` | N+1 yo'q, ≤6 query |
| `test_permission_revocation_is_immediate` | `apps/workspaces/tests.py` | R3 |
| `test_admin_cannot_edit_own_role_row` | `apps/workspaces/tests.py` | F-1 |
| `test_owner_only_codes_not_grantable` | `apps/workspaces/tests.py` | F-1 |
| `test_last_owner_invariants_survive_matrix` | `apps/workspaces/tests.py` | F-2 |
| `test_private_space_invisible_from_every_endpoint` (×8) | `apps/workspaces/tests.py` | F-3 |
| `test_backfill_preserves_visibility` | `apps/workspaces/tests.py` | R1 |
| `test_assignee_gets_auto_space_member` | `apps/tasks/tests.py` | AD-7 |
| `test_register_with_invite_token` (happy + 5 xato) | `apps/accounts/tests.py` | D.8 |
| `test_invite_lookup_throttled` | `apps/accounts/tests.py` | F-6 |
| `test_matrix_version_conflict_returns_409` | `apps/workspaces/tests.py` | D.3 |
| `makemigrations --check --dry-run` | CI | DATA_MODEL §13 gate |

Frontend E2E: `owner matritsani o'zgartiradi → member yangilaydi → tugma yo'qoladi`; `invite link → register → workspace'ga tushadi`.
