"""
LLM Language Support
Bilingual support for English and Arabic in the LLM system.

Features:
1. Language detection
2. Response language matching
3. Bilingual prompts and responses
4. RTL text handling for Arabic
5. Translation of key system terms

Part of the PREDICT Vehicle Intelligence Platform.
"""

import re
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum


class Language(Enum):
    """Supported languages"""
    ENGLISH = "en"
    ARABIC = "ar"


# Arabic character range for detection
ARABIC_PATTERN = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')


class LanguageSupport:
    """
    Provides bilingual support for the LLM system.

    Handles:
    - Language detection
    - Response language selection
    - Key term translations
    - Bilingual system prompts
    """

    # System identity in both languages
    SYSTEM_IDENTITY = {
        Language.ENGLISH: """You are the PREDICT AI - the artificial intelligence system that powers
vehicle predictive maintenance. When users ask questions, respond as if YOU are the one who:
- Analyzed the vehicle data
- Made the predictions
- Sent the notifications
- Learned from the collected data

Use first person ("I detected...", "I predicted...", "I sent this notification because...").

CRITICAL RULES:
1. NEVER make up or guess data - only use the context provided
2. If you don't have information, say "I don't have that data available"
3. Be specific with vehicle names, dates, and numbers from the context
4. When explaining predictions, reference the actual data that led to them
5. Be professional and helpful, but also honest about limitations""",

        Language.ARABIC: """أنت نظام PREDICT AI - نظام الذكاء الاصطناعي الذي يدير
الصيانة التنبؤية للمركبات. عندما يسأل المستخدمون أسئلة، أجب كأنك أنت من:
- حلل بيانات المركبة
- قام بالتنبؤات
- أرسل الإشعارات
- تعلم من البيانات المجمعة

استخدم صيغة المتكلم ("اكتشفت..."، "تنبأت..."، "أرسلت هذا الإشعار لأن...").

قواعد حاسمة:
1. لا تختلق أو تخمن البيانات أبداً - استخدم فقط السياق المقدم
2. إذا لم تكن لديك المعلومات، قل "ليست لدي هذه البيانات متاحة"
3. كن محدداً بأسماء المركبات والتواريخ والأرقام من السياق
4. عند شرح التنبؤات، أشر إلى البيانات الفعلية التي أدت إليها
5. كن مهنياً ومفيداً، لكن كن صادقاً أيضاً حول القيود"""
    }

    # Common terms translation dictionary
    TRANSLATIONS = {
        # Vehicle components
        "engine": {"ar": "المحرك", "en": "engine"},
        "transmission": {"ar": "ناقل الحركة", "en": "transmission"},
        "brakes": {"ar": "الفرامل", "en": "brakes"},
        "battery": {"ar": "البطارية", "en": "battery"},
        "oil": {"ar": "الزيت", "en": "oil"},
        "coolant": {"ar": "سائل التبريد", "en": "coolant"},
        "fuel": {"ar": "الوقود", "en": "fuel"},
        "tires": {"ar": "الإطارات", "en": "tires"},
        "suspension": {"ar": "نظام التعليق", "en": "suspension"},
        "steering": {"ar": "نظام التوجيه", "en": "steering"},
        "exhaust": {"ar": "العادم", "en": "exhaust"},
        "filter": {"ar": "الفلتر", "en": "filter"},

        # Alert priorities
        "critical": {"ar": "حرج", "en": "critical"},
        "high": {"ar": "عالي", "en": "high"},
        "medium": {"ar": "متوسط", "en": "medium"},
        "low": {"ar": "منخفض", "en": "low"},

        # Status terms
        "healthy": {"ar": "سليم", "en": "healthy"},
        "warning": {"ar": "تحذير", "en": "warning"},
        "danger": {"ar": "خطر", "en": "danger"},
        "maintenance required": {"ar": "يتطلب صيانة", "en": "maintenance required"},
        "service due": {"ar": "موعد الخدمة", "en": "service due"},

        # Prediction terms
        "prediction": {"ar": "تنبؤ", "en": "prediction"},
        "risk level": {"ar": "مستوى الخطر", "en": "risk level"},
        "confidence": {"ar": "الثقة", "en": "confidence"},
        "days until failure": {"ar": "أيام حتى العطل", "en": "days until failure"},
        "recommended action": {"ar": "الإجراء الموصى به", "en": "recommended action"},

        # Notification terms
        "notification": {"ar": "إشعار", "en": "notification"},
        "alert": {"ar": "تنبيه", "en": "alert"},
        "sent": {"ar": "مرسل", "en": "sent"},
        "delivered": {"ar": "تم التسليم", "en": "delivered"},
        "read": {"ar": "مقروء", "en": "read"},
        "acknowledged": {"ar": "تم الاستلام", "en": "acknowledged"},

        # Vehicle terms
        "vehicle": {"ar": "مركبة", "en": "vehicle"},
        "driver": {"ar": "سائق", "en": "driver"},
        "owner": {"ar": "مالك", "en": "owner"},
        "mileage": {"ar": "المسافة المقطوعة", "en": "mileage"},
        "km": {"ar": "كم", "en": "km"},

        # Common phrases
        "I detected": {"ar": "اكتشفت", "en": "I detected"},
        "I predicted": {"ar": "تنبأت", "en": "I predicted"},
        "I recommend": {"ar": "أوصي", "en": "I recommend"},
        "based on my analysis": {"ar": "بناءً على تحليلي", "en": "based on my analysis"},
        "the data shows": {"ar": "البيانات تظهر", "en": "the data shows"},
        "I sent this notification because": {"ar": "أرسلت هذا الإشعار لأن", "en": "I sent this notification because"},
        "I don't have that data available": {"ar": "ليست لدي هذه البيانات متاحة", "en": "I don't have that data available"},

        # Time terms
        "today": {"ar": "اليوم", "en": "today"},
        "yesterday": {"ar": "أمس", "en": "yesterday"},
        "last week": {"ar": "الأسبوع الماضي", "en": "last week"},
        "last month": {"ar": "الشهر الماضي", "en": "last month"},
        "days": {"ar": "أيام", "en": "days"},
        "hours": {"ar": "ساعات", "en": "hours"},
    }

    # Response templates in both languages
    RESPONSE_TEMPLATES = {
        "no_data": {
            Language.ENGLISH: "I don't have that data available. Could you provide more details or specify which vehicle you're asking about?",
            Language.ARABIC: "ليست لدي هذه البيانات متاحة. هل يمكنك تقديم المزيد من التفاصيل أو تحديد المركبة التي تسأل عنها؟"
        },
        "prediction_explanation": {
            Language.ENGLISH: "Based on my analysis of the vehicle data, I predicted a {risk_level}% risk of {component} failure. This prediction is based on: {factors}.",
            Language.ARABIC: "بناءً على تحليلي لبيانات المركبة، تنبأت بنسبة خطر {risk_level}% لعطل {component}. هذا التنبؤ مبني على: {factors}."
        },
        "notification_explanation": {
            Language.ENGLISH: "I sent this notification because I detected {issue} in {vehicle}. The priority was set to {priority} because {reason}.",
            Language.ARABIC: "أرسلت هذا الإشعار لأنني اكتشفت {issue} في {vehicle}. تم تعيين الأولوية على {priority} لأن {reason}."
        },
        "greeting": {
            Language.ENGLISH: "Hello! I'm PREDICT AI, your vehicle intelligence assistant. How can I help you today?",
            Language.ARABIC: "مرحباً! أنا PREDICT AI، مساعدك الذكي للمركبات. كيف يمكنني مساعدتك اليوم؟"
        },
        "confirmation": {
            Language.ENGLISH: "I understand. Let me check that for you.",
            Language.ARABIC: "فهمت. دعني أتحقق من ذلك لك."
        }
    }

    @classmethod
    def detect_language(cls, text: str) -> Language:
        """
        Detect the language of input text.

        Returns Language.ARABIC if text contains significant Arabic characters,
        otherwise returns Language.ENGLISH.
        """
        if not text:
            return Language.ENGLISH

        # Count Arabic characters
        arabic_chars = len(ARABIC_PATTERN.findall(text))
        total_letters = len([c for c in text if c.isalpha()])

        if total_letters == 0:
            return Language.ENGLISH

        # If more than 30% of letters are Arabic, consider it Arabic
        arabic_ratio = arabic_chars / total_letters
        return Language.ARABIC if arabic_ratio > 0.3 else Language.ENGLISH

    @classmethod
    def get_system_identity(cls, language: Language = None) -> str:
        """Get the system identity prompt in the specified language"""
        if language is None:
            language = Language.ENGLISH
        return cls.SYSTEM_IDENTITY.get(language, cls.SYSTEM_IDENTITY[Language.ENGLISH])

    @classmethod
    def translate_term(cls, term: str, target_language: Language) -> str:
        """
        Translate a key term to the target language.

        If no translation is found, returns the original term.
        """
        term_lower = term.lower()
        if term_lower in cls.TRANSLATIONS:
            lang_key = target_language.value
            return cls.TRANSLATIONS[term_lower].get(lang_key, term)
        return term

    @classmethod
    def get_template(cls, template_name: str, language: Language = None) -> str:
        """Get a response template in the specified language"""
        if language is None:
            language = Language.ENGLISH

        templates = cls.RESPONSE_TEMPLATES.get(template_name, {})
        return templates.get(language, templates.get(Language.ENGLISH, ""))

    @classmethod
    def format_response(
        cls,
        template_name: str,
        language: Language,
        **kwargs
    ) -> str:
        """
        Format a response using a template in the specified language.

        Translates any key terms in the kwargs to the target language.
        """
        template = cls.get_template(template_name, language)

        # Translate terms in kwargs
        translated_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, str):
                # Try to translate the value
                translated_kwargs[key] = cls.translate_term(value, language)
            else:
                translated_kwargs[key] = value

        try:
            return template.format(**translated_kwargs)
        except KeyError:
            return template

    @classmethod
    def create_bilingual_prompt(
        cls,
        english_content: str,
        arabic_content: str
    ) -> str:
        """
        Create a bilingual prompt with both English and Arabic content.

        Useful for system prompts that should work in both languages.
        """
        return f"""[English]
{english_content}

[Arabic / العربية]
{arabic_content}"""

    @classmethod
    def wrap_rtl(cls, text: str) -> str:
        """
        Wrap Arabic text with RTL markers for proper display.

        Adds Unicode RTL markers to ensure proper text direction.
        """
        # Right-to-Left Embedding
        RLE = '\u202B'
        # Pop Directional Formatting
        PDF = '\u202C'

        return f"{RLE}{text}{PDF}"

    @classmethod
    def get_bilingual_system_prompt(cls) -> str:
        """
        Get a bilingual system prompt that works for both languages.

        The LLM should automatically respond in the user's language.
        """
        return cls.create_bilingual_prompt(
            cls.SYSTEM_IDENTITY[Language.ENGLISH],
            cls.SYSTEM_IDENTITY[Language.ARABIC]
        ) + """

LANGUAGE INSTRUCTIONS:
- Detect the language of the user's message
- Respond in the SAME language the user used
- If the user switches languages, switch your response language accordingly
- For technical terms, you may use English terms with Arabic explanation in parentheses if responding in Arabic

تعليمات اللغة:
- اكتشف لغة رسالة المستخدم
- أجب بنفس اللغة التي استخدمها المستخدم
- إذا غير المستخدم اللغة، غير لغة ردك وفقاً لذلك
- للمصطلحات التقنية، يمكنك استخدام المصطلحات الإنجليزية مع شرح عربي بين قوسين إذا كان الرد بالعربية"""


class NotificationTranslator:
    """
    Translates notification content for bilingual delivery.
    """

    # Notification title templates
    TITLE_TEMPLATES = {
        "prediction_alert": {
            Language.ENGLISH: "Prediction Alert: {vehicle_name}",
            Language.ARABIC: "تنبيه تنبؤي: {vehicle_name}"
        },
        "dtc_detected": {
            Language.ENGLISH: "DTC Detected: {vehicle_name}",
            Language.ARABIC: "تم اكتشاف كود عطل: {vehicle_name}"
        },
        "service_due": {
            Language.ENGLISH: "Service Due: {vehicle_name}",
            Language.ARABIC: "موعد الخدمة: {vehicle_name}"
        },
        "critical_alert": {
            Language.ENGLISH: "Critical Alert: {vehicle_name}",
            Language.ARABIC: "تنبيه حرج: {vehicle_name}"
        },
        "device_offline": {
            Language.ENGLISH: "Device Disconnected",
            Language.ARABIC: "الجهاز غير متصل"
        }
    }

    # Message body templates
    MESSAGE_TEMPLATES = {
        "prediction_risk": {
            Language.ENGLISH: "{component} shows {risk_level}% failure risk",
            Language.ARABIC: "{component} يظهر نسبة خطر عطل {risk_level}%"
        },
        "days_until_failure": {
            Language.ENGLISH: "Estimated failure within {days} days",
            Language.ARABIC: "العطل المتوقع خلال {days} أيام"
        },
        "service_required": {
            Language.ENGLISH: "{service_type} service is required",
            Language.ARABIC: "خدمة {service_type} مطلوبة"
        },
        "dtc_description": {
            Language.ENGLISH: "Code {code}: {description}",
            Language.ARABIC: "كود {code}: {description}"
        }
    }

    @classmethod
    def translate_notification(
        cls,
        notification_type: str,
        language: Language,
        **kwargs
    ) -> Tuple[str, str]:
        """
        Translate notification title and message.

        Returns:
            Tuple of (title, message) in the target language
        """
        # Get title
        title_templates = cls.TITLE_TEMPLATES.get(notification_type, {})
        title = title_templates.get(language, title_templates.get(Language.ENGLISH, "Alert"))

        # Get appropriate message template
        if notification_type == "prediction_alert":
            msg_templates = cls.MESSAGE_TEMPLATES.get("prediction_risk", {})
        elif notification_type == "dtc_detected":
            msg_templates = cls.MESSAGE_TEMPLATES.get("dtc_description", {})
        elif notification_type == "service_due":
            msg_templates = cls.MESSAGE_TEMPLATES.get("service_required", {})
        else:
            msg_templates = {}

        message = msg_templates.get(language, msg_templates.get(Language.ENGLISH, ""))

        # Translate component names if present
        if "component" in kwargs:
            kwargs["component"] = LanguageSupport.translate_term(
                kwargs["component"], language
            )

        # Format templates
        try:
            title = title.format(**kwargs)
            message = message.format(**kwargs)
        except KeyError:
            pass

        return title, message

    @classmethod
    def create_bilingual_notification(
        cls,
        notification_type: str,
        **kwargs
    ) -> Dict[str, Tuple[str, str]]:
        """
        Create notification content in both languages.

        Returns:
            Dict with 'en' and 'ar' keys, each containing (title, message) tuple
        """
        return {
            "en": cls.translate_notification(notification_type, Language.ENGLISH, **kwargs),
            "ar": cls.translate_notification(notification_type, Language.ARABIC, **kwargs)
        }


# Convenience functions
def detect_language(text: str) -> str:
    """Detect language and return language code ('en' or 'ar')"""
    return LanguageSupport.detect_language(text).value


def get_system_prompt(language: str = "en") -> str:
    """Get system prompt for the specified language"""
    lang = Language.ARABIC if language == "ar" else Language.ENGLISH
    return LanguageSupport.get_system_identity(lang)


def get_bilingual_prompt() -> str:
    """Get bilingual system prompt"""
    return LanguageSupport.get_bilingual_system_prompt()


def translate(term: str, target_language: str = "ar") -> str:
    """Translate a term to the target language"""
    lang = Language.ARABIC if target_language == "ar" else Language.ENGLISH
    return LanguageSupport.translate_term(term, lang)
