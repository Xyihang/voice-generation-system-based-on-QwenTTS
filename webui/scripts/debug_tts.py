import argparse
import sys
import os
import gc
import re
import time
import json
import numpy as np

def split_text(text, max_chars=50):
    sentences = re.split(r'([.!?.,!?:;])', text)
    
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
    parser = argparse.ArgumentParser(description='Qwen3-TTS Debug Mode')
    parser.add_argument('--mode', type=str, required=True, choices=['generate', 'clone'], help='Mode: generate or clone')
    parser.add_argument('--model_path', type=str, required=True)
    parser.add_argument('--text', type=str, required=True)
    parser.add_argument('--output', type=str, required=True)
    parser.add_argument('--language', type=str, default='Chinese')
    parser.add_argument('--speaker', type=str, default='Vivian')
    parser.add_argument('--ref_audio', type=str, default=None, help='Reference audio for clone mode')
    parser.add_argument('--ref_text', type=str, default=None, help='Reference text for clone mode')
    parser.add_argument('--use_chunks', action='store_true', help='Enable text chunking')
    parser.add_argument('--max_chars', type=int, default=50, help='Max chars per chunk')
    parser.add_argument('--device', type=str, default='auto', help='Device: auto, cuda, cpu')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()
    model = None
    prompt = None

    debug_info = {
        'mode': args.mode,
        'text_length': len(args.text),
        'use_chunks': args.use_chunks,
        'device': args.device,
        'chunks': [],
        'generated': [],
        'errors': [],
        'timings': {}
    }

    start_time = time.time()

    try:
        import torch
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel

        torch.backends.cudnn.enabled = False
        torch.backends.cudnn.benchmark = False
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        
        if args.verbose:
            print('[INFO] cuDNN and TF32 disabled')

        aggressive_memory_cleanup()
        
        if args.verbose:
            print('[0/5] Memory cleared')

        debug_info['timings']['memory_cleanup'] = time.time() - start_time

        print('[1/5] Loading model...')
        
        use_cpu = False
        if args.device == 'cpu':
            use_cpu = True
            if args.verbose:
                print('[INFO] Using CPU mode (user specified)')
        elif args.device == 'auto' and torch.cuda.is_available():
            gpu_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            if args.verbose:
                print(f'[INFO] GPU total memory: {gpu_total:.2f} GB')
            if gpu_total < 6.0:
                use_cpu = True
                if args.verbose:
                    print(f'[INFO] GPU memory ({gpu_total:.1f}GB) < 6GB, switching to CPU mode')
        
        load_start = time.time()
        if use_cpu:
            if args.verbose:
                print('[INFO] Loading model on CPU (this may take longer)...')
            model = Qwen3TTSModel.from_pretrained(
                args.model_path,
                device_map="cpu",
                torch_dtype=torch.float32,
                attn_implementation='eager',
                low_cpu_mem_usage=True,
            )
            debug_info['device'] = 'cpu'
            if args.verbose:
                print('[INFO] Model loaded on CPU')
        else:
            if args.verbose:
                print('[INFO] Loading model on GPU...')
            model = Qwen3TTSModel.from_pretrained(
                args.model_path,
                device_map="cuda",
                dtype=torch.float16,
                attn_implementation='eager',
            )
            debug_info['device'] = 'cuda'
            if args.verbose:
                print('[INFO] Model loaded on GPU')
        
        debug_info['timings']['model_load'] = time.time() - load_start

        # Clone mode specific
        if args.mode == 'clone':
            if not args.ref_audio or not args.ref_text:
                raise ValueError('Clone mode requires --ref_audio and --ref_text')
            
            if args.verbose:
                print('[2/5] Creating voice clone prompt...')
            
            ref_audio_path = args.ref_audio
            if args.verbose:
                print(f'[DEBUG] Original ref_audio: {ref_audio_path}')
            
            is_windows_abs = len(ref_audio_path) > 2 and ref_audio_path[1] == ':' and ref_audio_path[2] in ('\\', '/')
            
            if not is_windows_abs:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                relative_path = ref_audio_path.lstrip('/').replace('/', os.sep)
                ref_audio_path = os.path.join(base_dir, relative_path)
            
            if args.verbose:
                print(f'[DEBUG] Resolved ref_audio_path: {ref_audio_path}')
                print(f'[DEBUG] File exists: {os.path.exists(ref_audio_path)}')
            
            if not os.path.exists(ref_audio_path):
                raise FileNotFoundError(f'Audio file not found: {ref_audio_path}')

            prompt_start = time.time()
            prompt = model.create_voice_clone_prompt(
                ref_audio=ref_audio_path,
                ref_text=args.ref_text,
            )
            debug_info['timings']['prompt_create'] = time.time() - prompt_start

        # Text chunking
        if args.use_chunks:
            text_chunks = split_text(args.text, args.max_chars)
            if args.verbose:
                print(f'[INFO] Text split into {len(text_chunks)} chunks (chunking enabled)')
                for i, chunk in enumerate(text_chunks):
                    debug_info['chunks'].append({
                        'index': i+1,
                        'text': chunk,
                        'length': len(chunk)
                    })
                    if args.verbose:
                        print(f'  Chunk {i+1}: "{chunk}" ({len(chunk)} chars)')
        else:
            text_chunks = [args.text]
            if args.verbose:
                print(f'[INFO] Using full text without chunking ({len(args.text)} chars)')
            debug_info['chunks'].append({
                'index': 1,
                'text': args.text,
                'length': len(args.text)
            })

        aggressive_memory_cleanup()

        if args.mode == 'clone':
            if args.verbose:
                print('[3/5] Generating speech with cloned voice...')
        else:
            if args.verbose:
                print('[2/5] Generating speech...')
        
        all_audio = []
        sr = None
        
        gen_start = time.time()
        for i, chunk in enumerate(text_chunks):
            if args.verbose:
                print(f'[INFO] Generating chunk {i+1}/{len(text_chunks)}: "{chunk[:30]}..."')
            
            chunk_start = time.time()
            
            try:
                if args.mode == 'clone':
                    wavs, sr = model.generate_voice_clone(
                        text=chunk,
                        language=args.language,
                        voice_clone_prompt=prompt,
                    )
                else:
                    if hasattr(model, 'generate_custom_voice'):
                        wavs, sr = model.generate_custom_voice(
                            text=chunk,
                            language=args.language,
                            speaker=args.speaker,
                            instruct=args.instruct if hasattr(args, 'instruct') and args.instruct else None
                        )
                    else:
                        wavs, sr = model.generate(
                            text=chunk,
                            language=args.language,
                        )
                
                chunk_time = time.time() - chunk_start
                all_audio.append(wavs[0].copy())
                del wavs
                
                debug_info['generated'].append({
                    'chunk_index': i+1,
                    'duration_samples': len(all_audio[-1]),
                    'time_seconds': round(chunk_time, 2)
                })
                
                if args.verbose:
                    print(f'[INFO] Chunk {i+1} generated successfully in {chunk_time:.2f}s')
                    
            except Exception as e:
                debug_info['errors'].append({
                    'chunk_index': i+1,
                    'error': str(e),
                    'type': type(e).__name__
                })
                if args.verbose:
                    print(f'[ERROR] Chunk {i+1} failed: {e}')
                raise
        
        debug_info['timings']['generation'] = time.time() - gen_start

        if not all_audio:
            raise RuntimeError("No audio chunks were generated successfully")

        concat_start = time.time()
        if args.verbose:
            print('[INFO] Concatenating audio chunks...')
        final_audio = np.concatenate(all_audio)
        debug_info['timings']['concat'] = time.time() - concat_start

        if args.verbose:
            print('[4/5] Saving audio...')
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        
        save_start = time.time()
        sf.write(args.output, final_audio, sr)
        debug_info['timings']['save'] = time.time() - save_start

        debug_info['timings']['total'] = time.time() - start_time
        debug_info['output_file'] = args.output
        debug_info['total_duration'] = f'{len(final_audio) / sr:.2f} seconds'
        debug_info['success'] = True

        if args.verbose:
            print('[5/5] Done!')
            print(f'Output saved to: {args.output}')
            print(f'Total duration: {len(final_audio) / sr:.2f} seconds')
            print(f'\n=== DEBUG INFO ===')
            print(json.dumps(debug_info, indent=2, ensure_ascii=False))

    except ImportError as e:
        debug_info['errors'].append({
            'type': 'ImportError',
            'error': str(e)
        })
        print(f'Error: Missing required package - {e}', file=sys.stderr)
        print('Please install qwen-tts: pip install qwen-tts', file=sys.stderr)
        debug_info['success'] = False
        debug_info['timings']['total'] = time.time() - start_time
        print(json.dumps(debug_info, indent=2, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        debug_info['errors'].append({
            'type': type(e).__name__,
            'error': str(e)
        })
        if args.verbose:
            print(f'Error: {e}', file=sys.stderr)
            import traceback
            traceback.print_exc()
        debug_info['success'] = False
        debug_info['timings']['total'] = time.time() - start_time
        print(json.dumps(debug_info, indent=2, ensure_ascii=False))
        sys.exit(1)
    finally:
        try:
            del prompt
        except:
            pass
        if model is not None:
            del model
        aggressive_memory_cleanup()
        if args.verbose:
            print('[CLEANUP] Memory released')

if __name__ == '__main__':
    main()
