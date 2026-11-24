# 🎬 StoryMotion AI

**Motor de criação de vídeos narrativos com Python, imagens e animações.**

O StoryMotion AI transforma um projeto JSON em um vídeo **MP4 (H.264)**, combinando fotografias, imagens PNG com transparência, movimentos de câmera, animações de camadas, transições, narração e legendas manuais ou automáticas. Foi pensado para histórias visuais, curiosidades, conteúdos educativos e vídeos verticais.

> Ferramenta de **linha de comando (CLI)** para montar vídeos narrativos a partir de cenas definidas em JSON.

## ✨ Funcionalidades

- Renderização de vídeos em **9:16** (1080 × 1920, por exemplo), com outras resoluções pares configuráveis.
- Imagens de fundo JPG/PNG, preservando a proporção mediante ajuste de enquadramento.
- Camadas de PNG transparente com posição, largura e opacidade configuráveis.
- Animações de camada: `none`, `fade_in`, `slide_in`, `pop_in`, `float_in`, `rise_in`, `spin_in`, `pulse`.
- Movimentos de câmera: `none`, `zoom_in`, `zoom_out`, `pan_horizontal`, `pan_vertical`, `ken_burns`, `cinematic_zoom`, `drift`.
- Transições: `cut`, `crossfade`, `fade_to_black`, `dip_to_black`, `slide_left`.
- Narração opcional por arquivo **MP3, WAV ou M4A**.
- Legendas incorporadas à imagem, com SRT manual ou transcrição local e destaque sincronizado por palavra.
- Validação do projeto JSON com Pydantic e exportação via FFmpeg.
- Resolução, FPS e qualidade de compressão configuráveis.

## 🧰 Requisitos

- **Python 3.12** (no Windows 11, use a edição de 64 bits).
- **FFmpeg** instalado com o codificador `libx264`, acessível pelo `PATH` ou indicado por `--ffmpeg`.
- Dependências em `requirements.txt`, incluindo Pillow, Pydantic e Faster-Whisper com uma versão compatível do PyAV.

Verifique o FFmpeg no PowerShell:

```powershell
ffmpeg -version
```

Se ainda não estiver instalado no Windows 11:

```powershell
winget install --id Gyan.FFmpeg -e
```

Feche e reabra o terminal após a instalação. Confira novamente com `ffmpeg -version`.

## 🚀 Instalação no Windows 11

Abra a pasta do projeto no VS Code e execute no PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Não é necessário ativar o ambiente virtual nesses comandos. Isso evita problemas com a política de execução de scripts do PowerShell.

### Primeira renderização

O pacote contém um exemplo do polvo com arquivos de mídia e legendas SRT:

```powershell
.\.venv\Scripts\python.exe main.py examples/polvo/polvo_com_legendas.json examples/polvo/polvo_final.mp4
```

O vídeo gerado será salvo em `examples/polvo/polvo_final.mp4`.

Para utilizar a instalação global de Python, você também pode executar:

```powershell
python main.py examples/polvo/polvo_com_legendas.json examples/polvo/polvo_final.mp4
```

**Importante:** `project` e `output` são **argumentos posicionais obrigatórios**, nesta ordem.

### FFmpeg fora do PATH

Se o programa informar `Adicione FFmpeg ao PATH ou forneça --ffmpeg`, passe o caminho real do executável:

```powershell
python main.py examples/polvo/polvo_com_legendas.json examples/polvo/polvo_final.mp4 --ffmpeg "C:\ffmpeg\bin\ffmpeg.exe"
```

O caminho `C:\ffmpeg\bin\ffmpeg.exe` é apenas ilustrativo.

## 📁 Estrutura

```text
storymotion-ai/
├── main.py
├── requirements.txt
├── pyproject.toml
├── README.md
├── storymotion/
│   ├── models.py          # Modelos e validação do JSON
│   ├── composition.py     # Câmera e composição das camadas
│   ├── motion.py          # Curvas e composição de transições
│   ├── subtitles.py       # SRT e desenho das legendas
│   ├── transcription.py   # Faster-Whisper e agrupamento por palavra
│   └── render.py          # Linha do tempo e exportação com FFmpeg
├── examples/
│   └── polvo/
│       ├── polvo.json
│       ├── polvo_com_legendas.json
│       ├── legendas_exemplo.srt
│       └── assets/
│           ├── polvo_gigante_nas_profundezas.png
│           ├── polvo_no_abismo_anatomia_luminescente.png
│           ├── polvo_sob_raios_de_luz_submarinos.png
│           └── trio_de_corações_neon_brilhantes.png
└── tests/
    ├── test_render.py
    ├── test_subtitles.py
    └── test_transcription.py
```

Os arquivos de mídia são resolvidos **em relação à pasta em que está o JSON**, não necessariamente em relação à pasta de execução do terminal.

## 📝 Criar seu próprio vídeo

Crie uma pasta com um JSON e os arquivos de mídia:

```text
meu_video/
├── historia.json
├── legenda.srt
└── assets/
    ├── fundo.jpg
    ├── objeto.png
    └── narracao.mp3
```

Exemplo de `historia.json`:

```json
{
  "project_name": "Minha curiosidade",
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "audio": "assets/narracao.mp3",
  "subtitles": {
    "file": "legenda.srt",
    "style": "dynamic",
    "font_size": 64,
    "color": "#FFFFFF",
    "outline_color": "#000000",
    "outline_width": 5,
    "margin_bottom": 350
  },
  "scenes": [
    {
      "id": "abertura",
      "duration": 8,
      "background": "assets/fundo.jpg",
      "camera_effect": "cinematic_zoom",
      "intensity": 0.4,
      "transition": "cut",
      "layers": [
        {
          "asset": "assets/objeto.png",
          "animation": "pop_in",
          "start": 0.5,
          "duration": 0.6,
          "x": 0.5,
          "y": 0.6,
          "width": 0.35,
          "opacity": 1
        }
      ]
    }
  ]
}
```

Execute:

```powershell
python main.py meu_video/historia.json meu_video/video_final.mp4
```

### Campos principais

| Campo | Descrição |
| --- | --- |
| `project_name` | Nome do projeto. |
| `width`, `height` | Dimensões pares do vídeo, até 3840 pixels por eixo. |
| `fps` | `24`, `30` ou `60`. |
| `audio` | Caminho opcional para narração MP3, WAV ou M4A. |
| `subtitles` | Configuração opcional de SRT manual ou transcrição automática. |
| `scenes` | Lista ordenada de cenas; cada uma exige `id`, `duration` e `background`. |
| `camera_effect` | Movimento de câmera aplicado ao fundo. |
| `camera_easing` | Curva da câmera. O padrão é `smoothstep`. |
| `intensity` | Intensidade do movimento, entre `0` e `1`. |
| `layers` | Lista de imagens sobrepostas, na ordem de composição. |
| `layers[].start` | Segundo de início da animação, **relativo à cena**. |
| `layers[].duration` | Duração da animação da camada. |
| `layers[].x`, `y` | Posição normalizada do centro (`0` a `1`). |
| `layers[].width` | Largura relativa à largura do quadro (`0` a `1`). |
| `layers[].opacity` | Opacidade entre `0` e `1`. |
| `transition` | Efeito aplicado na saída para a próxima cena. |
| `transition_easing` | Curva da transição. O padrão é `smoothstep`. |
| `transition_duration` | Duração da transição entre cenas. |

**Duração final:** o total pode ser menor que a soma de `duration` das cenas, porque `crossfade`, `dip_to_black` e `slide_left` sobrepõem trechos de cenas consecutivas. Para vídeos destinados a programas que exigem mais de um minuto, verifique a duração real do MP4.

## 🔊 Narração e legendas

### Narração

Adicione o arquivo de narração à pasta do projeto e informe no JSON:

```json
"audio": "assets/narracao.mp3"
```

O renderizador incorpora o arquivo como áudio AAC. Se for mais curto que o vídeo, o restante será preenchido com silêncio; se for longo, será cortado na duração final. **Não há geração automática de voz nem sincronização automática das cenas com o texto.**

### Legendas SRT

Crie um arquivo `legenda.srt`, por exemplo:

```srt
1
00:00:00,000 --> 00:00:03,000
Você sabia que os polvos têm três corações?

2
00:00:03,000 --> 00:00:06,000
Dois bombeiam sangue para as brânquias!
```

Inclua no JSON:

```json
"subtitles": {
  "file": "legenda.srt",
  "style": "dynamic",
  "font_size": 64,
  "color": "#FFFFFF",
  "outline_color": "#000000",
  "outline_width": 5,
  "margin_bottom": 350
}
```

- `clean`: legenda estática por frase.
- `dynamic`: frase com entrada visual suave.
- `font_file`: caminho opcional de fonte TTF compatível.

O SRT manual fornece os tempos das frases. As legendas são **gravadas nos quadros do vídeo**.

### Transcrição automática e destaque por palavra

Informe `audio` com a narração em MP3 ou WAV e use `subtitles.transcription` no lugar de `subtitles.file`. Este trecho é um objeto JSON com os dois campos a incorporar ao projeto:

```json
{
  "audio": "assets/narracao.mp3",
  "subtitles": {
    "transcription": {
      "model": "base",
      "language": "pt",
      "words_per_cue": 5
    },
    "style": "karaoke",
    "highlight_color": "#FFE44D",
    "font_size": 64,
    "margin_bottom": 350
  }
}
```

O Faster-Whisper roda localmente em CPU com quantização INT8. Na primeira execução com um nome como `tiny` ou `base`, o modelo é baixado para o cache do Hugging Face. Com o modelo em cache, é possível transcrever offline. Também é possível fornecer o caminho absoluto de uma pasta local de modelo CTranslate2. A transcrição dispensa chaves e APIs pagas.

Omita `language` para detectar o idioma. `words_per_cue` aceita de 1 a 12 palavras e o agrupamento também respeita pausas de fala. O estilo `karaoke` usa os tempos individuais retornados pelo modelo para destacar a palavra ativa com cor e movimento. Os estilos `clean` e `dynamic` também aceitam transcrição automática e mostram a frase inteira.

```powershell
.\.venv\Scripts\python.exe main.py meu_video/historia.json meu_video/saida.mp4 --export-srt meu_video/saida.srt
```

`--export-srt` grava um novo arquivo com os tempos das frases, limitado à duração final do vídeo. O destaque por palavra fica incorporado no MP4. Revise a transcrição e os tempos antes de publicar, sobretudo com áudio ruidoso ou com música. A duração e a ordem das cenas continuam definidas pelo JSON.

## 🎞️ Efeitos disponíveis

| Tipo | Valores aceitos |
| --- | --- |
| Câmera | `none`, `zoom_in`, `zoom_out`, `pan_horizontal`, `pan_vertical`, `ken_burns`, `cinematic_zoom`, `drift` |
| Camada | `none`, `fade_in`, `slide_in`, `pop_in`, `float_in`, `rise_in`, `spin_in`, `pulse` |
| Transição | `cut`, `crossfade`, `fade_to_black`, `dip_to_black`, `slide_left` |
| Easing | `smoothstep`, `smootherstep`, `sine_in_out`, `linear` |
| Legendas | `clean`, `dynamic`, `karaoke` |

Use `camera_easing: "smootherstep"` em uma cena para aceleração e desaceleração graduais no início e no fim. `sine_in_out` oferece uma curva senoidal e `linear` mantém a progressão constante.

`rise_in` sobe e revela o PNG, `spin_in` gira e revela a camada até estabilizar, e `pulse` aumenta a escala uma vez antes de voltar ao tamanho original. Todos respeitam a transparência do PNG e a opacidade da camada.

`slide_left` desliza as duas cenas para a esquerda. `dip_to_black` escurece a cena atual e revela a próxima dentro da sobreposição, com pelo menos três quadros. `fade_to_black` mantém o comportamento anterior, escurecendo a cena atual antes do corte. `transition_easing` controla o andamento desses efeitos.

> As animações atuais são efeitos programados sobre imagens estáticas; elas não equivalem a geração de vídeo por IA ou animação 3D.

## ⚙️ Opções da CLI

```powershell
python main.py --help
```

Sintaxe:

```text
python main.py PROJECT_JSON OUTPUT_MP4 [--ffmpeg CAMINHO] [--crf N] [--export-srt CAMINHO]
```

- `--ffmpeg`: caminho explícito para `ffmpeg.exe`, quando fora do `PATH`.
- `--crf`: qualidade H.264 de `0` a `51` (padrão `20`; valores menores tendem a resultar em melhor qualidade e arquivos maiores).
- `--export-srt`: exporta as legendas da transcrição para um novo SRT.

## ✅ Testes

Execute:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

A suíte cobre compatibilidade com os exemplos, efeitos, sincronização e exportação. Os testes automatizados de transcrição usam dados controlados e dispensam downloads de modelos. Os testes de MP4 usam FFmpeg e FFprobe quando disponíveis.

## 🛠️ Solução de problemas

**`ModuleNotFoundError: No module named 'PIL'`**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

A biblioteca instalada chama-se `Pillow`, embora o import seja `PIL`.

**`ModuleNotFoundError: No module named 'pydantic'`**

Instale as dependências no mesmo interpretador usado para executar o projeto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**`Adicione FFmpeg ao PATH ou forneça --ffmpeg`**

Verifique `ffmpeg -version`; instale o executável ou use `--ffmpeg` apontando para o arquivo correto.

**`the following arguments are required: project, output`**

Informe o JSON e o destino MP4:

```powershell
python main.py examples/polvo/polvo.json examples/polvo/saida.mp4
```

**Imagem não encontrada**

Confira se o nome do arquivo e o caminho relativo à pasta do JSON estão corretos.

**Vídeo sem narração**

Confira se `audio` existe no nível principal do JSON e se o arquivo MP3/WAV/M4A está acessível.

## 🗺️ Próximas melhorias

- Interface desktop em CustomTkinter.
- Editor visual de cenas e pré-visualização.
- Presets narrativos e efeitos parallax em múltiplas camadas.
- Ajustes mais precisos para sincronização de imagens e narração.

## 📌 Uso responsável

Use imagens, músicas, vídeos e narrações com licenças adequadas. Revise os fatos científicos antes de publicar. O uso do StoryMotion AI não garante que um vídeo será considerado original ou monetizável por TikTok, YouTube ou outras plataformas.

---

**StoryMotion AI** — projeto Python para experimentar narrativa visual, motion design e automação de edição.
