/**
 * Lug'at jadvallarining TO'LIQLIGI (reja §17.4).
 *
 * `Record<TaskStatus, string>` tipi yetishmayotgan kalitni kompilyatsiyada
 * ushlaydi, lekin uchta narsani ushlamaydi va aynan shular shu yerda
 * tekshiriladi:
 *
 *   1. bo'sh satr (`review: ""` tipga to'g'ri keladi);
 *   2. tartib massivi (`STATUS_ORDER` / `PRIORITY_ORDER`) jadvaldan
 *      ajralib qolishi — yangi kod qo'shilib, tartibga tushmasligi;
 *   3. `STATUS_COLOR` ning `globals.css` dagi `--color-status-*` tokenlaridan
 *      ajralib ketishi — lug'at faylining o'zi buni MAJBURIY deb yozgan
 *      (`uz.ts` sarlavha izohi, 6-band), lekin hech narsa tekshirmasdi.
 */

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  DUE_BUCKET_LABEL,
  PRIORITY_CLASS,
  PRIORITY_LABEL,
  PRIORITY_ORDER,
  STATUS_BG_CLASS,
  STATUS_COLOR,
  STATUS_LABEL,
  STATUS_ORDER,
} from "@/i18n/uz";
import { BUCKET_ORDER } from "@/lib/task-buckets";

const GLOBALS_CSS = path.resolve(import.meta.dirname, "../app/globals.css");

describe("status jadvallari", () => {
  it("har bir kod uchun bo'sh bo'lmagan yorliq, rang va sinf bor", () => {
    for (const status of STATUS_ORDER) {
      expect(STATUS_LABEL[status]?.trim(), status).toBeTruthy();
      expect(STATUS_COLOR[status], status).toMatch(/^#[0-9a-f]{6}$/);
      expect(STATUS_BG_CLASS[status]?.trim(), status).toBeTruthy();
    }
  });

  it("tartib massivi jadval kalitlari bilan bir xil to'plam", () => {
    expect([...STATUS_ORDER].sort()).toEqual(Object.keys(STATUS_LABEL).sort());
    expect([...STATUS_ORDER].sort()).toEqual(Object.keys(STATUS_COLOR).sort());
    expect([...STATUS_ORDER].sort()).toEqual(Object.keys(STATUS_BG_CLASS).sort());
    expect(new Set(STATUS_ORDER).size).toBe(STATUS_ORDER.length);
  });

  it("yorliqlar takrorlanmaydi", () => {
    const labels = STATUS_ORDER.map((s) => STATUS_LABEL[s]);
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("ranglar `globals.css` dagi `--color-status-*` tokenlariga teng", () => {
    const css = fs.readFileSync(GLOBALS_CSS, "utf8");
    for (const status of STATUS_ORDER) {
      // `in_progress` → `--color-status-in-progress`
      const token = `--color-status-${status.replace(/_/g, "-")}`;
      const match = css.match(new RegExp(`${token}:\\s*(#[0-9a-fA-F]{6})`));
      expect(match, `${token} topilmadi`).not.toBeNull();
      expect(match?.[1].toLowerCase()).toBe(STATUS_COLOR[status]);
    }
  });
});

describe("muhimlik jadvallari", () => {
  it("har bir kod uchun bo'sh bo'lmagan yorliq va sinf bor", () => {
    for (const priority of PRIORITY_ORDER) {
      expect(PRIORITY_LABEL[priority]?.trim(), priority).toBeTruthy();
      expect(PRIORITY_CLASS[priority]?.trim(), priority).toBeTruthy();
    }
  });

  it("tartib massivi jadval kalitlari bilan bir xil to'plam", () => {
    expect([...PRIORITY_ORDER].sort()).toEqual(Object.keys(PRIORITY_LABEL).sort());
    expect([...PRIORITY_ORDER].sort()).toEqual(Object.keys(PRIORITY_CLASS).sort());
    expect(new Set(PRIORITY_ORDER).size).toBe(PRIORITY_ORDER.length);
  });

  it("yorliqlar takrorlanmaydi", () => {
    const labels = PRIORITY_ORDER.map((p) => PRIORITY_LABEL[p]);
    expect(new Set(labels).size).toBe(labels.length);
  });
});

describe("muddat guruhlari", () => {
  it("`BUCKET_ORDER` dagi har bir kalit uchun yorliq bor", () => {
    for (const bucket of BUCKET_ORDER) {
      expect(DUE_BUCKET_LABEL[bucket]?.trim(), bucket).toBeTruthy();
    }
    expect([...BUCKET_ORDER].sort()).toEqual(Object.keys(DUE_BUCKET_LABEL).sort());
  });
});
