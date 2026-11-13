"""Real Redis input, worker processing, zipper serialization, ACK and PEL recovery."""
import importlib
import json
import os
import uuid

import pytest


@pytest.fixture
def worker(monkeypatch, real_service_modules):
    if not os.getenv('RUN_DOCUMENTSERVICE_REDIS_TESTS'):
        pytest.skip('Set RUN_DOCUMENTSERVICE_REDIS_TESTS=1 with an isolated Redis')
    import redis
    prefix = 'documentservice-test-' + uuid.uuid4().hex
    settings = {
        'REDIS_HOST': os.environ['REDIS_HOST'], 'REDIS_PORT': os.environ['REDIS_PORT'],
        'REDIS_PASSWORD': os.environ['REDIS_PASSWORD'],
        'DOCUMENTSERVICE_STREAM_KEY': prefix + '-input', 'DOCUMENTSERVICE_GROUP_NAME': prefix + '-group',
        'DOCUMENTSERVICE_CONSUMER_NAME_PREFIX': prefix, 'HOSTNAME': 'pytest',
        'ZIPPER_STREAM_KEY': prefix + '-output', 'ZIPPER_REDIS_HOST': os.environ['REDIS_HOST'],
        'ZIPPER_REDIS_PORT': os.environ['REDIS_PORT'], 'ZIPPER_REDIS_PASSWORD': os.environ['REDIS_PASSWORD'],
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    module = importlib.import_module('rstreamio.reader.documentservicestreamreader')
    client = module.redisstreamdbnew
    stream = client.Stream(settings['DOCUMENTSERVICE_STREAM_KEY'])
    group = settings['DOCUMENTSERVICE_GROUP_NAME']
    stream.create_group(group, '0', ignore_exists=True)
    try:
        yield module, client, stream, group, settings['ZIPPER_STREAM_KEY']
    finally:
        client.delete(settings['DOCUMENTSERVICE_STREAM_KEY'], settings['ZIPPER_STREAM_KEY'])
        client.close()


@pytest.mark.parametrize('category,failure', [('responsepackage', False), ('publicationpackage', False), ('responsepackage', True)])
def test_byte_message_to_zipper_and_ack(worker, monkeypatch, category, failure):
    module, client, stream, group, output = worker
    original = {'filename': 'source.pdf', 's3uripath': 'https://synthetic/source.pdf'}
    summary = {'filename': 'Résumé.pdf', 's3uripath': 'https://synthetic/summary.pdf'}
    generated = []
    def generate(self, payload):
        generated.append(payload)
        assert category != 'publicationpackage', 'Publication must bypass summary generation'
        assert json.loads(payload)['category'] == category
        if failure:
            raise RuntimeError('synthetic CDOGS failure')
        return [summary]
    monkeypatch.setattr(module.redactionsummaryservice, 'processmessage', generate)
    payload = {'jobid': '1', 'category': category, 'requesttype': 'general',
               'filestozip': json.dumps([original]), 'attributes': '[]', 'summarydocuments': '{}'}
    mid = client.xadd(stream.stream_key, payload)
    messages = stream.read_group(group, 'old-consumer', 1, 100, '>')
    assert messages[0][0] == mid
    assert client.xpending(stream.stream_key, group)['pending'] == 1
    # Existing groups survive restart; reclaim a pending job rather than replaying history.
    stream.create_group(group, '0', ignore_exists=True)
    reclaimed = stream.autoclaim(group, 'restarted-consumer', 0, '0-0', 1)
    assert reclaimed[0][0] == mid
    module.processmessage(*reclaimed[0], stream)
    assert len(generated) == (0 if category == 'publicationpackage' else 1)
    outgoing = client.xrange(output)
    assert len(outgoing) == 1
    body = outgoing[0][1]
    expected = [original] if failure or category == 'publicationpackage' else [original, summary]
    assert json.loads(body[b'filestozip']) == expected
    assert b'requesttype' not in body
    assert json.loads(body[b'attributes']) == '[]'
    assert json.loads(body[b'summarydocuments']) == '{}'
    assert client.xpending(stream.stream_key, group)['pending'] == 0
