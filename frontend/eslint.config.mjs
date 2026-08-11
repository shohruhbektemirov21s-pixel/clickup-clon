import js from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

const eslintConfig = defineConfig([
  globalIgnores([
    "dist/**",
    "build/**",
    "coverage/**",
    // Playwright artefaktlari — bundled minified JS, bizning kodimiz emas.
    // `.gitignore` da bor, lekin ESLint uni o'zi chetlab o'tmaydi, shuning
    // uchun bitta E2E yugurishidan keyin `npm run lint` qizil bo'lib qolardi.
    "playwright-report/**",
    "test-results/**",
  ]),

  js.configs.recommended,
  ...tseslint.configs.recommended,

  {
    files: ["**/*.{ts,tsx,mts,mjs}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: { "react-hooks": reactHooks },
    rules: {
      // NEGA TO'PLAM EMAS, IKKITA QOIDA: `eslint-plugin-react-hooks@7` ning
      // `recommended-latest` to'plami React Compiler qoidalarini ham yoqadi
      // (`immutability`, `purity`, `set-state-in-effect` …). Ular mavjud
      // kodda o'nlab xato beradi va ularni tuzatish framework
      // migratsiyasining ishi emas — alohida bosqichda yoqiladi. Bu ikkitasi
      // esa `eslint-config-next` da ham aynan shu darajada yoqilgan edi.
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      // Ishlatilmagan `_` prefiksli argument — atayin qoldirilgan deb hisoblanadi.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },

  // Vite Fast Refresh: modul faqat komponent eksport qilsagina ishlaydi.
  // `configs.vite` `allowConstantExport` ni yoqadi — o'zgarmas eksport
  // (masalan `DEFAULT_TITLE`) refresh'ni buzmaydi.
  //
  // `components/ui/**` CHETLAB O'TILADI: bular shadcn'dan ko'chirilgan
  // fayllar va ular ATAYLAB komponent yonida `cva` variantlarini
  // (`buttonVariants`, `badgeVariants`) eksport qiladi. Ularni bo'lish —
  // vendor fayllarni keyingi `shadcn add` da qo'lda birlashtirish demak.
  {
    files: ["src/**/*.tsx"],
    ignores: ["src/components/ui/**"],
    ...reactRefresh.configs.vite,
    rules: {
      ...reactRefresh.configs.vite.rules,
      // NEGA `warn`: bu qoida to'g'riligi emas, dev-tajribasi haqida — HMR
      // shunday faylni butunlay qayta yuklaydi, xolos. Uchta fayl (masalan
      // `password-strength.tsx` dagi `scorePassword`) yordamchi funksiyani
      // komponent yonida saqlaydi; ularni bo'lish alohida refaktoring va
      // framework migratsiyasining ishi emas.
      "react-refresh/only-export-components": "warn",
    },
  },

  // -------------------------------------------------------------------------
  // Yangi hardcoded o'zbekcha matnni bloklash
  // -------------------------------------------------------------------------
  //
  // Interfeys matni `src/i18n/uz.ts` da yashaydi. Bu qoida JSX ichiga
  // to'g'ridan-to'g'ri yozilgan o'zbekcha matn tugunini ushlaydi.
  //
  // NEGA REGEX SHU DARAJADA TOR: o'zbek lotin alifbosining yagona ishonchli
  // belgisi — `o'` / `g'` juftligi (apostrof ASCII `'`, tipografik `’`/`‘`
  // yoki to'g'ri `ʻ` bo'lishi mumkin). Bundan kengroq qoida (masalan "har
  // qanday harf") sinf nomlari, `&nbsp;`, tinish belgilari va inglizcha
  // qisqartmalarni ham ushlab, shovqinga aylanardi. `JSXText[value=…]` —
  // parser entity'ni ochib beradi, ya'ni `bo&apos;lim` ham topiladi.
  //
  // NEGA `error`: ko'chirish TUGADI — daraxtda birorta ham hardcoded o'zbekcha
  // JSX matni qolmadi. `warn` bo'lganida qoida bor edi, lekin DARVOZA yo'q edi:
  // CI yashil qolaverardi va yangi matn jimgina kirib kelardi. `error` shuni
  // yopadi — endi `npm run lint` (ya'ni CI) yangi hardcoded matnni to'xtatadi.
  {
    files: ["src/**/*.{jsx,tsx}"],
    ignores: ["src/i18n/**"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXText[value=/[oOgG]['’‘ʻ]|ʻ/]",
          message:
            "JSX ichida o'zbekcha matn yozilmasin — uni `src/i18n/uz.ts` lug'atiga qo'shing va shu yerdan chaqiring.",
        },
      ],
    },
  },
]);

export default eslintConfig;
