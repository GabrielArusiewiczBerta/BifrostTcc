from adapters.adapter import Adapter
from random import choice
from string import ascii_letters, digits, whitespace
from evaluation_tests.test_error import InputSizeError


def generate_passwords(n, length=10, prints=False):
    # generate a specified number of random passwords of fixed length (10 chars default)
    passwords = [(''.join(choice(ascii_letters + digits) for j in range(length))) for i in range(n)]
    if prints:
        print("generated", n, "passwords:", passwords)
    return passwords


def generate_string_of_length(sizes, prints=False):
    input_strings = [(''.join(choice(ascii_letters + digits + whitespace) for j in range(sizes[i]))) for i in
                     range(len(sizes))]
    if prints:
        print("generated input strings:\n\t", input_strings)
    return input_strings


def verify_sizes(sizes, strings, prints=False):
    verification = [Adapter.get_text_size(strings[i]) for i in range(len(strings))]
    if prints:
        print("verified input sizes:", verification)
    if verification != sizes:
        raise InputSizeError("Sizes of generated strings not according to input_sizes!")


def generate_encryption_size_data(base=2, n=13, prints=False):
    # prepare input parameters
    input_sizes = [base ** i for i in range(n)]
    if prints:
        print("using string sizes:", input_sizes)

    # generate input strings, source: https://stackoverflow.com/a/18319156
    input_strings = generate_string_of_length(input_sizes, prints)

    # double-check input lengths
    verify_sizes(input_sizes, input_strings, prints)

    # perform encryption with constant password
    password = generate_passwords(1, 10)
    # password = "very secure"
    encrypted_strings = [Adapter.encrypt(input_strings[i], password[0])[0] for i in range(n)]
    if prints:
        print("\nencrypted strings (using constant password):\n\t", encrypted_strings)

    # perform size check on encrypted strings
    encrypted_strings_sizes = [Adapter.get_text_size(encrypted_strings[i]) for i in range(n)]
    if prints:
        print("encrypted string sizes:", encrypted_strings_sizes)

    # calculate percentage increase
    size_increase_percent = [((encrypted_strings_sizes[i] - input_sizes[i])/(input_sizes[i])) * 100 for i in range(n)]
    if prints:
        print("encrypted strings size increase:", size_increase_percent)

    # return generated data
    return input_strings, input_sizes, encrypted_strings, encrypted_strings_sizes, size_increase_percent

# generate_encryption_size_data(prints=True)
