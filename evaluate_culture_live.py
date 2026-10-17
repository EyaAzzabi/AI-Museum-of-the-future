"""Small live retrieval benchmark from Sarah's observed failures, not a training set."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from agents.culture_art import CultureArtAgent
from agents.culture_scope import analysis_status
from agents.llm_config import build_llm_client
from rag.vector_store.culture_retrieval import build_supabase_client, retrieve_culture
from rag.vector_store.culture_reranker import CultureReranker, DEFAULT_CACHE_DIR

KNOWN_ARTIST = '1cab8304-42df-40c2-b55f-c71f714074eb'
CASES = [
    ('specific_artist', 'Joe Luciano Tunisian rock music and freedom of expression'),
    ('broad_art', 'contemporary art and cultural identity in Tunisia'),
]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Required: authorizes real Supabase/LLM requests')
    parser.add_argument('--baseline', action='store_true', help='Evaluate the V4 retrieval without reranking')
    parser.add_argument('--output', default='culture_evaluation_v5.json')
    args=parser.parse_args()
    if not args.live:
        parser.error('Use --live to run two real queries (up to 20 screening calls plus two generation calls).')
    load_dotenv(Path(__file__).resolve().parent / '.env')
    db=build_supabase_client()
    report={'method':'v4_baseline' if args.baseline else 'v5',
            'notice':'Two known regression cases; not an independent quality benchmark. Human review required.',
            'cases':[]}
    for name,query in CASES:
        info={}
        try:
            chunks=retrieve_culture(query,db,country='Tunisia',diagnostics=info,
                reranker=None if args.baseline else CultureReranker(build_llm_client, cache_dir=DEFAULT_CACHE_DIR))
            insight=CultureArtAgent(build_llm_client() if chunks else None).run(chunks,query=query,country='Tunisia')
            report['cases'].append({'name':name,'query':query,
                'known_source_retrieved':any(r.chunk_id==KNOWN_ARTIST for r in chunks),
                'known_source_cited':KNOWN_ARTIST in insight.selected_artifacts,
                'retrieval':info, 'evidence':[asdict(r) for r in chunks],
                **analysis_status(insight,chunks,query,'Tunisia',info), 'insight':asdict(insight),
                'human_review':{'topic_relevance':None,'claims_supported':None,
                               'self_description_attributed':None,'no_national_generalization':None}})
        except Exception as exc:
            report['cases'].append({'name':name,'error_type':type(exc).__name__,
                'status':'execution_failed','human_review':None})
    output=Path(args.output)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Report: {output}. Inspect evidence and human_review before claiming improvement.')
    return 1 if any(c.get('status')=='execution_failed' for c in report['cases']) else 0


if __name__=='__main__':
    raise SystemExit(main())
