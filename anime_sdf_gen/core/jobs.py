"""Helpers for consuming cooperative numerical jobs."""


def run(generator):
    while True:
        try:
            next(generator)
        except StopIteration as done:
            return done.value
