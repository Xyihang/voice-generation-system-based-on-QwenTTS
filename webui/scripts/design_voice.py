import argparse
import sys
import os
import gc
import re
import time
import json
import numpy as np

def split_text(text, max_chars=50):
    sentences = re.split(r'([。！？.!?，,、；;：])', text)
    
    chunks = []
    current = ""
    
    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        if i + 1 < len(sentences):
            sentence += sentences[i + 1]
        
        if len(current) + len(sentence) <= max_chars:
            current += sentence
        else:
            if current:
                chunks.append(current.strip())
            if len(sentence) > max_chars:
                for j in range(0, len(sentence), max_chars):
                    chunks.append(sentence[j:j+max_chars].strip())
                current = ""
            else:
                current = sentence
    
    if current.strip():
        chunks.append(current.strip())
    
    return [c for c in chunks if c]

def aggressive_memory_cleanup():
    for _ in range(3):
        gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except:
        pass

def main():
    parser = argparse.ArgumentParser(description='Qwen3-TTS Voice Design')
    parser.add_argument('--config', type=str, help='JSON config file path')
    parser.add_argument('--model_path', type=str)
    parser.add_argument('--text', type=str)
    parser.add_argument('--output', type=str)
    parser.add_argument('--language', type=str, default='Chinese')
    parser.add_argument('--instruct', type=str, default='')
    parser.add_argument('--use_chunks', action='store_true', help='Enable text chunking')
    parser.add_argument('--max_chars', type=int, default=50, help='Max chars per chunk (only if use_chunks)')
    parser.add_argument('--device', type=str, default='auto', help='Device: auto, cuda, cpu')

    args = parser.parse_args()

    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        args.model_path = cfg.get('model_path', args.model_path)
        args.text = cfg.get('text', args.text)
        args.output = cfg.get('output', args.output)
        args.language = cfg.get('language', args.language)
        args.instruct = cfg.get('instruct', args.instruct or '')
        args.device = cfg.get('device', args.device)

    args.model_path = os.path.abspath(args.model_path)
    args.output = os.path.abspath(args.output)
    model = None

    try:
        if not os.environ.get('HF_ENDPOINT'):
            os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        import torch
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel

        torch.backends.cudnn.enabled = False
        torch.backends.cudnn.benchmark = False
        try:
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
        except:
            pass
        print('[INFO] cuDNN and TF32 disabled')

        aggressive_memory_cleanup()
        print('[0/5] Memory cleared')

        print('[1/5] Loading model...')
        
        use_cpu = False
        if args.device == 'cpu':
            use_cpu = True
            print('[INFO] Using CPU mode (user specified)')
        elif args.device == 'auto' and torch.cuda.is_available():
            gpu_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f'[INFO] GPU total memory: {gpu_total:.2f} GB')
            if gpu_total < 6.0:
                use_cpu = True
                print(f'[INFO] GPU memory ({gpu_total:.1f}GB) < 6GB, switching to CPU mode')
        elif not torch.cuda.is_available():
            use_cpu = True
            print('[INFO] CUDA not available, using CPU mode')
        
        if use_cpu:
            print('[INFO] Loading model on CPU (this may take longer)...')
            model = Qwen3TTSModel.from_pretrained(
                args.model_path,
                device_map="cpu",
                dtype=torch.float32,
                attn_implementation='eager',
                low_cpu_mem_usage=True,
            )
            print('[INFO] Model loaded on CPU')
        else:
            print('[INFO] Loading model on GPU...')
            model = Qwen3TTSModel.from_pretrained(
                args.model_path,
                device_map="cuda",
                dtype=torch.float16,
                attn_implementation='eager',
            )
            print('[INFO] Model loaded on GPU')

        if args.use_chunks:
            text_chunks = split_text(args.text, args.max_chars)
            print(f'[INFO] Text split into {len(text_chunks)} chunks (chunking enabled)')
            for i, chunk in enumerate(text_chunks):
                print(f'  Chunk {i+1}: "{chunk}" ({len(chunk)} chars)')
        else:
            text_chunks = [args.text]
            print(f'[INFO] Using full text without chunking ({len(args.text)} chars)')

        aggressive_memory_cleanup()

        print('[2/5] Generating speech with designed voice...')
        
        all_audio = []
        sr = None
        
        for i, chunk in enumerate(text_chunks):
            print(f'[INFO] Generating chunk {i+1}/{len(text_chunks)}: "{chunk}"')
            
            max_retries = 3
            for retry in range(max_retries):
                aggressive_memory_cleanup()
                
                if torch.cuda.is_available() and not use_cpu:
                    mem_before = torch.cuda.memory_allocated(0) / 1024**3
                    print(f'[MEM] Before: {mem_before:.2f}GB')
                
                try:
                    wavs, sr = model.generate_voice_design(
                        text=chunk,
                        language=args.language,
                        instruct=args.instruct if args.instruct else None
                    )
                    all_audio.append(wavs[0].copy())
                    del wavs
                    break
                except RuntimeError as e:
                    if "out of memory" in str(e).lower():
                        print(f'[WARN] OOM on chunk {i+1}, retry {retry+1}/{max_retries}...')
                        aggressive_memory_cleanup()
                        time.sleep(2)
                        if retry == max_retries - 1:
                            raise RuntimeError(f"Failed to generate chunk {i+1} after {max_retries} retries: OOM")
                    else:
                        raise
            
            aggressive_memory_cleanup()
            print(f'[INFO] Chunk {i+1} generated successfully')

        if not all_audio:
            raise RuntimeError("No audio chunks were generated successfully")

        print('[INFO] Concatenating audio chunks...')
        final_audio = np.concatenate(all_audio)

        print('[3/5] Saving audio...')
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        sf.write(args.output, final_audio, sr)

        print('[4/5] Done!')
        print(f'Output saved to: {args.output}')
        print(f'Total duration: {len(final_audio) / sr:.2f} seconds')
        sys.stdout.flush()

    except ImportError as e:
        print(f'Error: Missing required package - {e}', file=sys.stderr)
        print('Please install qwen-tts: pip install qwen-tts', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if model is not None:
            del model
        try:
            aggressive_memory_cleanup()
        except Exception:
            pass
        print('[CLEANUP] Memory released')
        sys.stdout.flush()

if __name__ == '__main__':
    main()