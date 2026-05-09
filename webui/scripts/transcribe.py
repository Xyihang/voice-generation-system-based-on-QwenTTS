import argparse
import sys
import os
import gc
import time
import json

def main():
    parser = argparse.ArgumentParser(description='Whisper Turbo Audio Transcription')
    parser.add_argument('--config', type=str, help='JSON config file path')
    parser.add_argument('--audio_path', type=str)
    parser.add_argument('--output', type=str)
    parser.add_argument('--language', type=str, default='zh')
    parser.add_argument('--device', type=str, default='auto')

    args = parser.parse_args()

    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        args.audio_path = cfg.get('audio_path', args.audio_path)
        args.output = cfg.get('output', args.output)
        args.language = cfg.get('language', args.language)
        args.device = cfg.get('device', args.device)

    if not args.audio_path or not os.path.exists(args.audio_path):
        print('[ERROR] Audio file not found: {}'.format(args.audio_path), flush=True)
        sys.exit(1)

    if not args.output:
        print('[ERROR] Output path not specified', flush=True)
        sys.exit(1)

    args.audio_path = os.path.abspath(args.audio_path)
    args.output = os.path.abspath(args.output)

    try:
        import torch
        import whisper

        os.environ['OMP_NUM_THREADS'] = str(os.cpu_count())
        os.environ['MKL_NUM_THREADS'] = str(os.cpu_count())
        torch.set_num_threads(os.cpu_count())
        torch.set_num_interop_threads(1)

        print('[1/4] Preparing turbo model...', flush=True)

        model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'whisper_models')
        os.makedirs(model_dir, exist_ok=True)

        pt_path = os.path.join(model_dir, 'large-v3-turbo.pt')

        if os.path.exists(pt_path):
            try:
                checkpoint = torch.load(pt_path, map_location='cpu', weights_only=False)
                if 'dims' in checkpoint and 'model_state_dict' in checkpoint:
                    print('[INFO] Cached turbo model found', flush=True)
                else:
                    os.remove(pt_path)
                    pt_path = None
            except Exception:
                os.remove(pt_path)
                pt_path = None

        if not os.path.exists(pt_path):
            print('[2/4] Downloading turbo model (first time only)...', flush=True)

            try:
                from huggingface_hub import hf_hub_download
                sf_path = hf_hub_download(
                    repo_id='openai/whisper-large-v3-turbo',
                    filename='model.safetensors',
                    local_dir=model_dir,
                    local_dir_use_symlinks=False,
                )
            except Exception:
                if not os.environ.get('HF_ENDPOINT'):
                    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
                from huggingface_hub import hf_hub_download
                sf_path = hf_hub_download(
                    repo_id='openai/whisper-large-v3-turbo',
                    filename='model.safetensors',
                    local_dir=model_dir,
                    local_dir_use_symlinks=False,
                )

            print('[3/4] Converting model format...', flush=True)
            import re
            from safetensors.torch import load_file

            TURBO_CONFIG = {
                'n_mels': 128,
                'n_audio_ctx': 1500,
                'n_audio_state': 1280,
                'n_audio_head': 20,
                'n_audio_layer': 32,
                'n_vocab': 51866,
                'n_text_ctx': 448,
                'n_text_state': 1280,
                'n_text_head': 20,
                'n_text_layer': 4,
            }

            state_dict = load_file(sf_path)
            new_state_dict = {}
            for k, v in state_dict.items():
                new_key = re.sub(r'^model\.', '', k)
                new_key = new_key.replace('encoder.layers.', 'encoder.blocks.')
                new_key = new_key.replace('decoder.layers.', 'decoder.blocks.')
                new_key = new_key.replace('self_attn_layer_norm', 'attn_ln')
                new_key = new_key.replace('encoder_attn_layer_norm', 'cross_attn_ln')
                new_key = re.sub(r'self_attn\.k_proj', 'attn.key', new_key)
                new_key = re.sub(r'self_attn\.q_proj', 'attn.query', new_key)
                new_key = re.sub(r'self_attn\.v_proj', 'attn.value', new_key)
                new_key = re.sub(r'self_attn\.out_proj', 'attn.out', new_key)
                new_key = re.sub(r'encoder_attn\.k_proj', 'cross_attn.key', new_key)
                new_key = re.sub(r'encoder_attn\.q_proj', 'cross_attn.query', new_key)
                new_key = re.sub(r'encoder_attn\.v_proj', 'cross_attn.value', new_key)
                new_key = re.sub(r'encoder_attn\.out_proj', 'cross_attn.out', new_key)
                new_key = re.sub(r'\.fc1\b', '.mlp.0', new_key)
                new_key = re.sub(r'\.fc2\b', '.mlp.2', new_key)
                new_key = new_key.replace('final_layer_norm', 'mlp_ln')
                new_key = new_key.replace('encoder.layer_norm', 'encoder.ln_post')
                new_key = new_key.replace('decoder.layer_norm', 'decoder.ln')
                new_key = new_key.replace('encoder.embed_positions.weight', 'encoder.positional_embedding')
                new_key = new_key.replace('decoder.embed_positions.weight', 'decoder.positional_embedding')
                new_key = new_key.replace('decoder.embed_tokens', 'decoder.token_embedding')
                new_key = new_key.replace('proj_out.weight', 'decoder.proj_out.weight')
                new_state_dict[new_key] = v

            checkpoint = {'dims': TURBO_CONFIG, 'model_state_dict': new_state_dict}
            torch.save(checkpoint, pt_path)
            print('[INFO] Model converted: {} params'.format(len(state_dict)), flush=True)

        print('[INFO] Loading turbo model...', flush=True)

        use_cpu = True
        if args.device == 'cuda' and torch.cuda.is_available():
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
            if gpu_mem >= 6.0:
                use_cpu = False

        device = 'cpu' if use_cpu else 'cuda'
        print('[INFO] Device: {} | CPU cores: {}'.format(device, os.cpu_count()), flush=True)

        model = whisper.load_model(pt_path, device=device)
        model.eval()
        if use_cpu:
            torch.set_float32_matmul_precision('medium')

        print('[INFO] Model ready', flush=True)

        print('[4/4] Transcribing: {}'.format(os.path.basename(args.audio_path)), flush=True)

        file_size = os.path.getsize(args.audio_path) / 1024 / 1024
        print('[INFO] File size: {:.2f} MB'.format(file_size), flush=True)

        t0 = time.time()
        result = model.transcribe(
            args.audio_path,
            language=args.language,
            fp16=(device == 'cuda'),
        )
        elapsed = time.time() - t0

        text = result.get('text', '').strip()

        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text)

        print('[DONE] Transcription complete in {:.1f}s'.format(elapsed), flush=True)
        print('[RESULT] {}'.format(text), flush=True)
        print('[OUTPUT] {}'.format(args.output), flush=True)
        print('Output saved', flush=True)

    except Exception as e:
        print('[ERROR] Transcription failed: {}'.format(e), flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        model = None
        for _ in range(3):
            gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except:
            pass
        print('[CLEANUP] Done', flush=True)

if __name__ == '__main__':
    main()
