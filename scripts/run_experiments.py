#!/usr/bin/env python3
"""Reproduce controlled verification and within-judgment retrieval measurements."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from citation_verifier.core import Corpus, normalized_text
from citation_verifier.evaluation import evaluate_cases, generate_mutations, rank_bm25, split_judgment_ids


def retrieval_queries(rows):
    """Up to three deterministic fragments per judgment, capped at 47 tokens."""
    out = []
    for row in rows:
        count = 0
        for p in row['paragraphs']:
            tokens = normalized_text(p['text']).split()
            if len(tokens) < 12:
                continue
            tokens = tokens[:60]
            start = len(tokens) // 3
            stop = start + max(3, len(tokens) // 4)
            query = ' '.join((tokens[:start] + tokens[stop:])[:47])
            out.append({'judgment_id': row['id'], 'gold_paragraph': p['number'], 'query': query})
            count += 1
            if count == 3:
                break
    return out


def rank_summary(rows):
    ranks = [int(x['rank']) for x in rows]
    return {
        'count': len(ranks),
        'recall_at_1': sum(r <= 1 for r in ranks) / len(ranks) if ranks else 0.0,
        'recall_at_5': sum(r <= 5 for r in ranks) / len(ranks) if ranks else 0.0,
        'mrr': sum(1 / r for r in ranks) / len(ranks) if ranks else 0.0,
    }


def bm25_retrieval(corpus, queries, k1=1.5, b=0.75):
    rows = {r['id']: r for r in corpus.rows}
    result = []
    start = time.perf_counter()
    for q in queries:
        paras = rows[q['judgment_id']]['paragraphs']
        ranked = rank_bm25([p['text'] for p in paras], q['query'], k1=k1, b=b)
        rank = next(n for n, x in enumerate(ranked, 1) if paras[x['index']]['number'] == q['gold_paragraph'])
        result.append({**q, 'rank': rank})
    return {'summary': rank_summary(result), 'rows': result, 'elapsed_s': time.perf_counter() - start}


def dense_retrieval(corpus, dev_queries, test_queries, revision=None):
    # Cache is separate from project scripts; no repository code or pickle weights are loaded.
    os.environ['HF_HOME'] = str(ROOT / '.cache' / 'huggingface')
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ['HF_HUB_DISABLE_XET'] = '1'
    import torch
    from huggingface_hub import HfApi
    from sentence_transformers import SentenceTransformer
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable; no GPU result was generated')
    model_name = 'sentence-transformers/all-MiniLM-L6-v2'
    revision = revision or HfApi().model_info(model_name).sha
    if not revision or len(revision) != 40:
        raise ValueError('Expected an immutable 40-character model revision')
    start = time.perf_counter()
    model = SentenceTransformer(model_name, revision=revision, device='cuda',
                                cache_folder=os.environ['HF_HOME'], trust_remote_code=False,
                                model_kwargs={'use_safetensors': True})
    torch.set_num_threads(min(8, os.cpu_count() or 1))
    # Time batches on development paragraphs only; weights and ranking do not get fitted.
    dev_ids = {q['judgment_id'] for q in dev_queries}
    probe = [p['text'] for r in corpus.rows if r['id'] in dev_ids for p in r['paragraphs']][:128]
    model.encode(probe[:8], batch_size=8, show_progress_bar=False)
    trials = []
    for batch in (8, 16, 32):
        torch.cuda.synchronize()
        begin = time.perf_counter()
        model.encode(probe, batch_size=batch, normalize_embeddings=True, show_progress_bar=False)
        torch.cuda.synchronize()
        trials.append({'batch_size': batch, 'seconds': time.perf_counter() - begin, 'paragraphs': len(probe)})
    batch = min(trials, key=lambda t: t['seconds'])['batch_size']
    selected_ids = {q['judgment_id'] for q in dev_queries + test_queries}
    texts, offsets, numbers = [], {}, {}
    for row in corpus.rows:
        if row['id'] not in selected_ids:
            continue
        offsets[row['id']] = (len(texts), len(texts) + len(row['paragraphs']))
        texts.extend(p['text'] for p in row['paragraphs'])
        numbers[row['id']] = [p['number'] for p in row['paragraphs']]
    # Encode each paragraph once. Rank only within its judgment, never a global Q x D matrix.
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    begin = time.perf_counter()
    documents = model.encode(texts, batch_size=batch, normalize_embeddings=True, convert_to_tensor=True, show_progress_bar=True)
    torch.cuda.synchronize()
    indexing_seconds = time.perf_counter() - begin
    output = {}
    for split, queries in [('dev', dev_queries), ('test', test_queries)]:
        torch.cuda.synchronize()
        begin = time.perf_counter()
        vectors = model.encode([q['query'] for q in queries], batch_size=batch,
                               normalize_embeddings=True, convert_to_tensor=True, show_progress_bar=False)
        ranks = []
        for q, vector in zip(queries, vectors):
            lo, hi = offsets[q['judgment_id']]
            scores = (documents[lo:hi] @ vector).detach().cpu().tolist()
            order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
            gold = numbers[q['judgment_id']].index(q['gold_paragraph'])
            ranks.append({**q, 'rank': order.index(gold) + 1})
        torch.cuda.synchronize()
        output[split] = {'summary': rank_summary(ranks), 'rows': ranks, 'elapsed_s': time.perf_counter() - begin}
    return {
        'status': 'ok', 'model': model_name, 'revision': revision, 'device': 'cuda',
        'torch': torch.__version__, 'gpu': torch.cuda.get_device_name(0),
        'max_seq_length': model.max_seq_length, 'embedding_dimension': model.get_sentence_embedding_dimension(),
        'batch_size': batch, 'batch_trials_dev': trials, 'indexing_seconds': indexing_seconds,
        'encoded_paragraphs': len(texts), 'total_seconds': time.perf_counter() - start,
        'peak_cuda_memory_bytes': torch.cuda.max_memory_allocated(), **output,
    }


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf8')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', default=str(ROOT / 'data/corpus.jsonl'))
    ap.add_argument('--out', default=str(ROOT / 'results'))
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--skip-gpu', action='store_true')
    ap.add_argument('--model-revision', help='Reuse revision recorded by the original experiment')
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    corpus = Corpus.load(args.corpus)
    dev, test = split_judgment_ids(corpus, seed=args.seed)
    cases = {s: generate_mutations(corpus, judgment_ids=ids) for s, ids in [('dev', dev), ('test', test)]}
    for split in cases:
        (out / f'evaluation_{split}.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in cases[split]), encoding='utf8')
    evaluation = evaluate_cases(corpus, cases['test'])
    dump(out / 'evaluation.json', {'seed': args.seed, 'dev_judgments': dev, 'test_judgments': test, 'case_count': len(cases['test']), 'evaluation': evaluation})
    queries = {s: retrieval_queries([r for r in corpus.rows if r['id'] in set(ids)]) for s, ids in [('dev', dev), ('test', test)]}
    trials = []
    for k1 in (0.8, 1.5, 2.0):
        for b in (0.25, 0.75):
            result = bm25_retrieval(corpus, queries['dev'], k1=k1, b=b)
            trials.append({'k1': k1, 'b': b, **result['summary']})
    best = max(trials, key=lambda t: (t['mrr'], t['recall_at_1'], -t['k1'], -t['b']))
    retrieval = {
        'task': 'Within-judgment localization; first three eligible paragraphs; first 60 tokens with a gap removed, capped at 47 tokens. Automatic source-paragraph labels, overlap-heavy queries.',
        'selection_split': 'dev', 'bm25_grid': trials, 'bm25_selected': {'k1': best['k1'], 'b': best['b']},
        'bm25': bm25_retrieval(corpus, queries['test'], k1=best['k1'], b=best['b']),
    }
    dump(out / 'retrieval.json', retrieval)
    if args.skip_gpu:
        retrieval['dense'] = {'status': 'skipped', 'reason': 'Explicit --skip-gpu flag'}
    else:
        try:
            retrieval['dense'] = dense_retrieval(corpus, queries['dev'], queries['test'], args.model_revision)
        except Exception as exc:
            retrieval['dense'] = {'status': 'blocked', 'reason': f'{type(exc).__name__}: {exc}'}
            print('GPU experiment failed:', retrieval['dense']['reason'], file=sys.stderr)
    dump(out / 'retrieval.json', retrieval)
    versions = {}
    for name in ('torch', 'sentence-transformers', 'transformers', 'pymupdf', 'requests'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    manifest = {
        'created_at': datetime.now(timezone.utc).isoformat(), 'seed': args.seed,
        'corpus_sha256': hashlib.sha256(Path(args.corpus).read_bytes()).hexdigest(),
        'code_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), ROOT / 'src/citation_verifier/core.py', ROOT / 'src/citation_verifier/evaluation.py']},
        'corpus_rows': len(corpus.rows), 'paragraphs': sum(len(r['paragraphs']) for r in corpus.rows),
        'development_cases': len(cases['dev']), 'evaluation_cases': len(cases['test']),
        'dev_judgments': len(dev), 'test_judgments': len(test),
        'platform': platform.platform(), 'python': platform.python_version(), 'processor': platform.processor(),
        'packages': versions, 'gpu_status': retrieval['dense']['status'],
        'files': ['evaluation.json', 'evaluation_dev.jsonl', 'evaluation_test.jsonl', 'retrieval.json'],
    }
    dump(out / 'run_manifest.json', manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != 'code_sha256'}))
    return 1 if retrieval['dense']['status'] == 'blocked' else 0


if __name__ == '__main__':
    raise SystemExit(main())
