import phonenumbers


class PhoneNumbersNormalizer:
    def normalize(self, value: str, default_region: str) -> str:
        parsed = phonenumbers.parse(value, default_region)
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Phone number is invalid")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
