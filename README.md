# Family Health Android releases

هذا المستودع مخصّص لملفات APK المنشورة وبيانات الإصدارات فقط. لا يحتوي على كود المصدر أو أسرار أو قواعد بيانات.

- `manifests/production`: القناة التي تقرؤها تطبيقات العمل.
  التطبيقات: `accounting`، `warehouse`، `representatives` («مندوب بيع»)، و`representatives-delivery` («مندوب توصيل»، الحزمة `com.familyhealth.representatives.delivery`). لكل حزمة manifest مستقلة، وكل manifest ترفض حزمة غيرها.
- `manifests/qa`: قناة اختبار معزولة لا تقرؤها تطبيقات العمل.
- ملفات APK تُرفق في GitHub Releases ولا تُحفظ داخل تاريخ Git.

كل تطبيق يتحقق محليًا من اسم الحزمة ورقم الإصدار وبصمة SHA-256 وشهادة توقيع APK قبل فتح شاشة تثبيت Android.

## Workers وWorkers Receiver وFatora (manifests موقّعة)

هذه التطبيقات الثلاثة تقرأ نفس الجذر
`https://raw.githubusercontent.com/ahmedmmo902-byte/family-health-app-releases/main/manifests`
لكنها لا تقبل أي manifest إلا مع ملف توقيع منفصل `.sig` بجانبه:

| المنتج | package (production) | manifest | tag | اسم الأصل |
|---|---|---|---|---|
| Workers (المدير) | `com.example.workers` | `manifests/production/workers.json` + `.sig` | `workers-vX.Y.Z` | `workers-X.Y.Z.apk` |
| Workers Receiver | `com.example.workers.receiver` | `manifests/production/workers-receiver.json` + `.sig` | `workers-vX.Y.Z` (نفس الـRelease) | `workers-receiver-X.Y.Z.apk` |
| Fatora | `com.example.fatora` | `manifests/production/fatora.json` + `.sig` | `fatora-vX.Y.Z` | `fatora-X.Y.Z.apk` |

قناة QA تستخدم packages منفصلة (`….qa`) وملفات `manifests/qa/<app>.json` + `.sig` وtags من نوع prerelease (`workers-qa-vX.Y.Z` و`fatora-qa-vX.Y.Z`) ومفاتيح QA لا تثق بها نسخ الإنتاج.

- التوقيع Ed25519 على **البايتات الحرفية** لملف الـmanifest؛ أي تغيير ولو byte واحد (بما فيه تحويل نهايات الأسطر) يُفشل التحقق. لذلك يضبط `.gitattributes` ملفات `manifests/**/*.json` و`*.sig` على `-text`.
- صيغة ملف التوقيع تختلف بين المشروعين ولا تُوحَّد: Workers/Receiver `{"schema": 1, "alg": "Ed25519", "kid": "…", "sig": "…"}` وFatora `{"alg": "Ed25519", "kid": "…", "signature": "…"}`. تُستخدم دائمًا أداة كل مشروع نفسه (`tool/update/make_manifest.py`).
- `sequence` عدد صحيح يزيد دائمًا لكل (تطبيق، قناة) ولا يُعاد استخدامه.
- `status=published` هو مفتاح النشر الوحيد. السحب = manifest موقّعة بحالة غير منشورة (`paused`، أو `withdrawn` في Workers) و`sequence` أعلى. لا تُحذف tags ولا أصول ولا يُعاد استخدام رقم إصدار أو sequence.
- أول bridge update يكون `required=false`.
- لا APK ولا مفاتيح (keystore/PEM/properties/كلمات مرور) داخل Git إطلاقًا.

التفاصيل الكاملة وترتيب النشر والسحب: [`RELEASE_PROCESS.md`](RELEASE_PROCESS.md). التحقق من البايتات المنشورة: [`tools/verify_manifest_raw.py`](tools/verify_manifest_raw.py). تجهيز المرشحات: [`tools/stage_candidate.md`](tools/stage_candidate.md).
