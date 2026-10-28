import pytest


def test_reject_untrusted_urls_before_network():
    from trading_lab.sources import validate_url
    for url in ['http://kernc.github.io/', 'https://127.0.0.1/', 'https://kernc.github.io.evil.test/',
                'https://user:secret@kernc.github.io/', 'https://kernc.github.io:444/']:
        with pytest.raises(ValueError):
            validate_url(url)
    assert validate_url('https://kernc.github.io/backtesting.py/')
