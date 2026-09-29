# Family Health Android releases

هذا المستودع مخصّص لملفات APK المنشورة وبيانات الإصدارات فقط. لا يحتوي على كود المصدر أو أسرار أو قواعد بيانات.

- `manifests/production`: القناة التي تقرؤها تطبيقات العمل.
  التطبيقات: `accounting`، `warehouse`، `representatives` («مندوب بيع»)، و`representatives-delivery` («مندوب توصيل»، الحزمة `com.familyhealth.representatives.delivery`). لكل حزمة manifest مستقلة، وكل manifest ترفض حزمة غيرها.
- `manifests/qa`: قناة اختبار معزولة لا تقرؤها تطبيقات العمل.
- ملفات APK تُرفق في GitHub Releases ولا تُحفظ داخل تاريخ Git.

كل تطبيق يتحقق محليًا من اسم الحزمة ورقم الإصدار وبصمة SHA-256 وشهادة توقيع APK قبل فتح شاشة تثبيت Android.
