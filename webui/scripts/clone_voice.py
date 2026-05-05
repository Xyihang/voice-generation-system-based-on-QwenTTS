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
    parser = argparse.ArgumentParser(description='Qwen3-TTS Voice Clone')
    parser.add_argument('--config', type=str, help='JSON config file path')
    parser.add_argument('--model_path', type=str)
    parser.add_argument('--text', type=str)
    parser.add_argument('--ref_audio', type=str)
    parser.add_argument('--ref_text', type=str)
    parser.add_argument('--output', type=str)
    parser.add_argument('--language', type=str, default='Chinese')
    parser.add_argument('--instruct', type=str, default='')
    parser.add_argument('--use_chunks', action='store_true', help='Enable text chunking')
    parser.add_argument('--max_chars', type=int, default=50, help='Max chars per chunk (only if use_chunks)')

    args = parser.parse_args()

    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        args.model_path = cfg.get('model_path', args.model_path)
        args.text = cfg.get('text', args.text)
        args.ref_audio = cfg.get('ref_audio', args.ref_audio)
        args.ref_text = cfg.get('ref_text', args.ref_text)
        args.output = cfg.get('output', args.output)
        args.language = cfg.get('language', args.language)
        args.instruct = cfg.get('instruct', args.instruct or '')

    args.model_path = os.path.abspath(args.model_path)
    args.ref_audio = os.path.abspath(args.ref_audio)
    args.output = os.path.abspath(args.output)
    model = None
    prompt = None

    try:
        if not os.environ.get('HF_ENDPOINT'):
            os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        import torch
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel

        torch.backends.cudnn.enabled = False
        torch.backends.cudnn.benchmark = False
        print('[INFO] cuDNN disabled')

        aggressive_memory_cleanup()
        print('[0/5] Memory cleared')

        print('[1/5] Loading model on CPU...')
        
        model = Qwen3TTSModel.from_pretrained(
            args.model_path,
            device_map="cpu",
            dtype=torch.float32,
            attn_implementation='eager',
            low_cpu_mem_usage=True,
        )
        print('[INFO] Model loaded on CPU')

        print('[2/5] Creating voice clone prompt...')
        ref_audio_path = args.ref_audio
        print(f'[DEBUG] Original ref_audio: {ref_audio_path}')
        
        is_windows_abs = len(ref_audio_path) > 2 and ref_audio_path[1] == ':' and ref_audio_path[2] in ('\\', '/')
        
        if not is_windows_abs:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            relative_path = ref_audio_path.lstrip('/').replace('/', os.sep)
            ref_audio_path = os.path.join(base_dir, relative_path)
        
        print(f'[DEBUG] Resolved ref_audio_path: {ref_audio_path}')
        
        if not os.path.exists(ref_audio_path):
            raise FileNotFoundError(f'Audio file not found: {ref_audio_path}')

        if ref_audio_path.lower().endswith('.webm'):
            import subprocess
            converted_path = ref_audio_path + '.wav'
            print(f'[INFO] Converting webm to wav: {ref_audio_path}')
            result = subprocess.run(
                ['ffmpeg', '-y', '-i', ref_audio_path, '-ar', '24000', '-ac', '1', converted_path],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                raise RuntimeError(f'ffmpeg conversion failed: {result.stderr}')
            ref_audio_path = converted_path
            print(f'[INFO] Converted to: {converted_path}')

        prompt = model.create_voice_clone_prompt(
            ref_audio=ref_audio_path,
            ref_text=args.ref_text,
        )

        if 'converted_path' in locals() and os.path.exists(converted_path):
            try:
                os.remove(converted_path)
                print(f'[INFO] Cleaned up converted file: {converted_path}')
            except:
                pass

        # 根据参数决定是否分块
        if args.use_chunks:
            text_chunks = split_text(args.text, args.max_chars)
            print(f'[INFO] Text split into {len(text_chunks)} chunks (chunking enabled)')
            for i, chunk in enumerate(text_chunks):
                print(f'  Chunk {i+1}: "{chunk}" ({len(chunk)} chars)')
        else:
            text_chunks = [args.text]
            print(f'[INFO] Using full text without chunking ({len(args.text)} chars)')

        print('[3/5] Generating speech with cloned voice...')
        
        all_audio = []
        sr = None
        
        for i, chunk in enumerate(text_chunks):
            print(f'[INFO] Generating chunk {i+1}/{len(text_chunks)}: "{chunk[:30]}..."')
            
            wavs, sr = model.generate_voice_clone(
                text=chunk,
                language=args.language,
                voice_clone_prompt=prompt,
            )
            all_audio.append(wavs[0].copy())
            del wavs
            
            print(f'[INFO] Chunk {i+1} generated successfully')

        if not all_audio:
            raise RuntimeError("No audio chunks were generated successfully")

        print('[INFO] Concatenating audio chunks...')
        final_audio = np.concatenate(all_audio)

        print('[4/5] Saving audio...')
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        sf.write(args.output, final_audio, sr)

        print('[5/5] Done!')
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
        try:
            del prompt
        except:
            pass
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
