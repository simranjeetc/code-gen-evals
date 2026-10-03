def is_palindrome(s):
    cleaned = [char.lower() for char in s if char.isalnum()]
    return cleaned == cleaned[::-1]
