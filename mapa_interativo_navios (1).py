#!/usr/bin/env python3
"""
Mapa Interativo de Trajetórias de Navios
Desenvolvido com Folium para visualização interativa de dados de navegação
"""

import pandas as pd
import folium
from folium import plugins
import numpy as np
from datetime import datetime
import json

# ===========================
# 1. CARREGAR E PROCESSAR DADOS
# ===========================
print("Carregando dados do CSV combinado...")
df = pd.read_csv('/home/ubuntu/Uploads/consumo_combinado.csv')

# Converter DATAHORA para datetime
df['DATAHORA'] = pd.to_datetime(df['DATAHORA'])

# Remover duplicatas baseadas em timestamp, lat, lon e nome
df = df.drop_duplicates(subset=['NOME', 'DATAHORA', 'LATITUDE', 'LONGITUDE'])

# Ordenar por nome e data
df = df.sort_values(['NOME', 'DATAHORA']).reset_index(drop=True)

# Limpar valores NaN
df = df.dropna(subset=['LATITUDE', 'LONGITUDE', 'VELOCIDADE', 'RUMO'])

print(f"Total de pontos únicos: {len(df)}")
print(f"Navios: {df['NOME'].unique()}")
print(f"Período: {df['DATAHORA'].min()} até {df['DATAHORA'].max()}")

# ===========================
# 2. FUNÇÕES AUXILIARES
# ===========================

def velocidade_para_cor(velocidade, v_min, v_max):
    """Converte velocidade em cor do espectro verde-amarelo-vermelho"""
    if v_max == v_min:
        return '#00ff00'  # verde se todas velocidades iguais
    
    # Normalizar entre 0 e 1
    norm = (velocidade - v_min) / (v_max - v_min)
    
    if norm < 0.5:
        # Verde para Amarelo
        r = int(255 * (norm * 2))
        g = 255
        b = 0
    else:
        # Amarelo para Vermelho
        r = 255
        g = int(255 * (2 - norm * 2))
        b = 0
    
    return f'#{r:02x}{g:02x}{b:02x}'

def criar_icone_seta(angulo, cor):
    """Cria um ícone SVG de seta rotacionada"""
    svg = f'''
    <svg width="30" height="30" xmlns="http://www.w3.org/2000/svg">
        <g transform="rotate({angulo} 15 15)">
            <path d="M15 5 L20 20 L15 17 L10 20 Z" fill="{cor}" stroke="black" stroke-width="1"/>
        </g>
    </svg>
    '''
    return svg

def criar_popup_html(row):
    """Cria HTML para popup com informações do ponto"""
    html = f"""
    <div style="font-family: Arial; font-size: 12px; min-width: 200px;">
        <h4 style="margin: 0 0 10px 0; color: #2c3e50;">{row['NOME']}</h4>
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 5px; font-weight: bold;">Data/Hora:</td>
                <td style="padding: 5px;">{row['DATAHORA'].strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 5px; font-weight: bold;">Velocidade:</td>
                <td style="padding: 5px;">{row['VELOCIDADE']:.1f} km/h</td>
            </tr>
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 5px; font-weight: bold;">Rumo:</td>
                <td style="padding: 5px;">{row['RUMO']:.1f}°</td>
            </tr>
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 5px; font-weight: bold;">Latitude:</td>
                <td style="padding: 5px;">{row['LATITUDE']:.6f}</td>
            </tr>
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 5px; font-weight: bold;">Longitude:</td>
                <td style="padding: 5px;">{row['LONGITUDE']:.6f}</td>
            </tr>
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 5px; font-weight: bold;">Evento:</td>
                <td style="padding: 5px;">{row['eventName']}</td>
            </tr>
            <tr>
                <td style="padding: 5px; font-weight: bold;">Session ID:</td>
                <td style="padding: 5px; font-size: 10px;">{row['sessionId']}</td>
            </tr>
        </table>
    </div>
    """
    return html

# ===========================
# 3. CRIAR MAPA BASE
# ===========================
print("\nCriando mapa base...")

# Calcular centro do mapa baseado em todos os pontos
centro_lat = df['LATITUDE'].mean()
centro_lon = df['LONGITUDE'].mean()

# Criar mapa
mapa = folium.Map(
    location=[centro_lat, centro_lon],
    zoom_start=9,
    tiles='OpenStreetMap',
    control_scale=True
)

# Adicionar tile layers alternativos
folium.TileLayer('cartodbpositron', name='CartoDB Positron').add_to(mapa)
folium.TileLayer('cartodbdark_matter', name='CartoDB Dark').add_to(mapa)

# ===========================
# 4. PROCESSAR DADOS POR NAVIO
# ===========================
print("\nProcessando trajetórias dos navios...")

navios = df['NOME'].unique()
v_min = df['VELOCIDADE'].min()
v_max = df['VELOCIDADE'].max()

# Preparar dados para JSON (para filtros JavaScript)
dados_json = {}

for navio in navios:
    print(f"\nProcessando: {navio}")
    df_navio = df[df['NOME'] == navio].copy()
    
    # Criar feature group para este navio
    fg_navio = folium.FeatureGroup(name=navio, show=True)
    
    # Preparar coordenadas e dados para a trajetória
    coordenadas = []
    pontos_dados = []
    
    # Encontrar primeiro evento "EM PORTO" (equivalente a DOCAGEM)
    primeiro_porto_idx = None
    df_porto = df_navio[df_navio['eventName'] == 'EM PORTO']
    if len(df_porto) > 0:
        primeiro_porto_idx = df_porto.index[0]
    
    # ===========================
    # 5. ADICIONAR PONTOS E SETAS
    # ===========================
    for idx, row in df_navio.iterrows():
        lat, lon = row['LATITUDE'], row['LONGITUDE']
        coordenadas.append([lat, lon])
        
        # Cor baseada na velocidade
        cor = velocidade_para_cor(row['VELOCIDADE'], v_min, v_max)
        
        # Dados para JSON
        pontos_dados.append({
            'lat': lat,
            'lon': lon,
            'datahora': row['DATAHORA'].strftime('%Y-%m-%d %H:%M:%S'),
            'velocidade': float(row['VELOCIDADE']),
            'rumo': float(row['RUMO']),
            'evento': row['eventName'],
            'sessionId': str(row['sessionId']),
            'cor': cor
        })
        
        # Adicionar marcador circular pequeno em cada ponto
        folium.CircleMarker(
            location=[lat, lon],
            radius=3,
            popup=folium.Popup(criar_popup_html(row), max_width=300),
            tooltip=f"{row['DATAHORA'].strftime('%Y-%m-%d %H:%M')} - {row['VELOCIDADE']:.1f} km/h",
            color=cor,
            fill=True,
            fillColor=cor,
            fillOpacity=0.8,
            weight=2
        ).add_to(fg_navio)
        
        # Adicionar seta a cada N pontos para não poluir
        if len(df_navio) > 50:
            intervalo = len(df_navio) // 30  # Máximo 30 setas
        else:
            intervalo = 2
            
        if idx % intervalo == 0 or idx == df_navio.index[-1]:
            # Criar marcador com seta customizada
            icon_html = f'''
            <div style="transform: rotate({row['RUMO']}deg); transform-origin: center;">
                <svg width="30" height="30" xmlns="http://www.w3.org/2000/svg">
                    <path d="M15 5 L20 20 L15 17 L10 20 Z" fill="{cor}" stroke="black" stroke-width="1.5"/>
                </svg>
            </div>
            '''
            folium.Marker(
                location=[lat, lon],
                icon=folium.DivIcon(html=icon_html),
                tooltip=f"Rumo: {row['RUMO']:.1f}°"
            ).add_to(fg_navio)
    
    # ===========================
    # 6. ADICIONAR LINHA DE TRAJETÓRIA
    # ===========================
    # Criar segmentos coloridos da linha
    for i in range(len(coordenadas) - 1):
        cor = velocidade_para_cor(pontos_dados[i]['velocidade'], v_min, v_max)
        folium.PolyLine(
            locations=[coordenadas[i], coordenadas[i+1]],
            color=cor,
            weight=3,
            opacity=0.7,
            tooltip=f"Velocidade: {pontos_dados[i]['velocidade']:.1f} km/h"
        ).add_to(fg_navio)
    
    # ===========================
    # 7. ADICIONAR ÍCONE DE ÂNCORA
    # ===========================
    if primeiro_porto_idx is not None:
        row_porto = df_navio.loc[primeiro_porto_idx]
        
        # Ícone de âncora customizado
        ancora_html = '''
        <div style="font-size: 30px; color: #2c3e50; text-shadow: 2px 2px 4px rgba(0,0,0,0.5);">
            ⚓
        </div>
        '''
        
        folium.Marker(
            location=[row_porto['LATITUDE'], row_porto['LONGITUDE']],
            icon=folium.DivIcon(html=ancora_html),
            popup=folium.Popup(f"""
            <div style="font-family: Arial; font-size: 12px;">
                <h4 style="margin: 0 0 10px 0; color: #2c3e50;">⚓ Primeiro EM PORTO</h4>
                <p><b>Navio:</b> {row_porto['NOME']}</p>
                <p><b>Data/Hora:</b> {row_porto['DATAHORA'].strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><b>Localização:</b> {row_porto['LATITUDE']:.6f}, {row_porto['LONGITUDE']:.6f}</p>
            </div>
            """, max_width=300),
            tooltip="⚓ Primeiro evento EM PORTO"
        ).add_to(fg_navio)
        
        print(f"  ⚓ Âncora adicionada em: {row_porto['DATAHORA']}")
    
    # Adicionar feature group ao mapa
    fg_navio.add_to(mapa)
    
    # Salvar dados para JSON
    dados_json[navio] = pontos_dados
    
    # Informações do session ID
    session_ids = df_navio['sessionId'].unique()
    print(f"  Session IDs: {session_ids}")
    print(f"  Total de pontos: {len(df_navio)}")

# ===========================
# 8. ADICIONAR LEGENDA
# ===========================
print("\nAdicionando legenda...")

# Criar legenda HTML
legenda_html = f'''
<div style="
    position: fixed; 
    bottom: 50px; 
    left: 50px; 
    width: 280px; 
    background-color: white; 
    border: 2px solid grey; 
    z-index: 9999; 
    font-size: 14px;
    padding: 10px;
    border-radius: 5px;
    box-shadow: 0 0 15px rgba(0,0,0,0.2);
    font-family: Arial, sans-serif;
">
    <h4 style="margin: 0 0 10px 0; text-align: center; color: #2c3e50;">📍 Legenda</h4>
    
    <div style="margin-bottom: 10px;">
        <b>Espectro de Velocidade:</b><br/>
        <div style="display: flex; align-items: center; margin-top: 5px;">
            <div style="width: 100%; height: 20px; background: linear-gradient(to right, #00ff00, #ffff00, #ff0000); border: 1px solid #333;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 2px;">
            <span>{v_min:.1f} km/h</span>
            <span>{v_max:.1f} km/h</span>
        </div>
    </div>
    
    <div style="margin-bottom: 10px;">
        <b>Símbolos:</b><br/>
        <div style="margin-top: 5px;">
            <span style="font-size: 20px;">⚓</span> = Primeiro evento EM PORTO<br/>
            <span style="font-size: 20px;">➤</span> = Direção do rumo<br/>
            <span style="font-size: 20px;">●</span> = Ponto de trajetória
        </div>
    </div>
    
    <div>
        <b>Session IDs:</b><br/>
        <div style="font-size: 11px; margin-top: 5px; max-height: 100px; overflow-y: auto;">
'''

# Adicionar session IDs únicos
for navio in navios:
    df_navio = df[df['NOME'] == navio]
    session_ids = df_navio['sessionId'].unique()
    legenda_html += f'<b>{navio}:</b><br/>'
    for sid in session_ids:
        legenda_html += f'• {sid}<br/>'

legenda_html += '''
        </div>
    </div>
</div>
'''

mapa.get_root().html.add_child(folium.Element(legenda_html))

# ===========================
# 9. ADICIONAR CONTROLES E FILTROS
# ===========================
print("\nAdicionando controles interativos...")

# Adicionar controle de camadas
folium.LayerControl(position='topright', collapsed=False).add_to(mapa)

# Adicionar plugin de tela cheia
plugins.Fullscreen(
    position='topright',
    title='Tela cheia',
    title_cancel='Sair da tela cheia',
    force_separate_button=True
).add_to(mapa)

# Adicionar medidor de distâncias
plugins.MeasureControl(
    position='topleft',
    primary_length_unit='kilometers',
    secondary_length_unit='meters',
    primary_area_unit='sqkilometers',
    secondary_area_unit='hectares'
).add_to(mapa)

# ===========================
# 10. ADICIONAR FILTROS HTML/JavaScript
# ===========================
print("\nAdicionando filtros interativos...")

# Preparar lista de datas únicas para o filtro
datas_unicas = sorted(df['DATAHORA'].dt.date.unique())
data_min = datas_unicas[0].strftime('%Y-%m-%d')
data_max = datas_unicas[-1].strftime('%Y-%m-%d')

filtros_html = f'''
<div id="filtros" style="
    position: fixed;
    top: 10px;
    left: 50px;
    background-color: white;
    padding: 15px;
    border: 2px solid #2c3e50;
    border-radius: 8px;
    z-index: 9999;
    box-shadow: 0 0 15px rgba(0,0,0,0.3);
    font-family: Arial, sans-serif;
    min-width: 300px;
">
    <h3 style="margin: 0 0 15px 0; color: #2c3e50; text-align: center;">🗺️ Filtros do Mapa</h3>
    
    <div style="margin-bottom: 15px;">
        <label style="font-weight: bold; display: block; margin-bottom: 5px;">
            🚢 Selecionar Navio (um por vez):
        </label>
        <select id="filtro-navio" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">
'''

# Adicionar primeiro navio como selecionado por padrão
for i, navio in enumerate(navios):
    selected = ' selected' if i == 0 else ''
    filtros_html += f'            <option value="{navio}"{selected}>{navio}</option>\n'

filtros_html += f'''
        </select>
    </div>
    
    <div style="margin-bottom: 15px;">
        <label style="font-weight: bold; display: block; margin-bottom: 5px;">
            📅 Data Inicial:
        </label>
        <input type="date" id="filtro-data-inicio" value="{data_min}" min="{data_min}" max="{data_max}"
               style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">
    </div>
    
    <div style="margin-bottom: 15px;">
        <label style="font-weight: bold; display: block; margin-bottom: 5px;">
            📅 Data Final:
        </label>
        <input type="date" id="filtro-data-fim" value="{data_max}" min="{data_min}" max="{data_max}"
               style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">
    </div>
    
    <button onclick="aplicarFiltros()" style="
        width: 100%;
        padding: 10px;
        background-color: #3498db;
        color: white;
        border: none;
        border-radius: 4px;
        font-size: 16px;
        font-weight: bold;
        cursor: pointer;
        transition: background-color 0.3s;
    " onmouseover="this.style.backgroundColor='#2980b9'" 
       onmouseout="this.style.backgroundColor='#3498db'">
        🔍 Aplicar Filtros
    </button>
    
    <div id="info-filtros" style="
        margin-top: 10px;
        padding: 8px;
        background-color: #ecf0f1;
        border-radius: 4px;
        font-size: 12px;
        text-align: center;
        color: #2c3e50;
    ">
        Mostrando todos os dados
    </div>
</div>

<script>
// Dados dos navios em JSON
var dadosNavios = {json.dumps(dados_json)};
var naviosDisponiveis = {json.dumps(list(navios))};

// Função para encontrar e controlar os layers dos navios
function controlarLayersNavios(navioSelecionado) {{
    // Encontrar todos os overlays (feature groups)
    var overlayMaps = document.querySelectorAll('.leaflet-control-layers-overlays label');
    
    overlayMaps.forEach(function(label) {{
        var span = label.querySelector('span');
        if (span) {{
            var nomeLayer = span.textContent.trim();
            var checkbox = label.querySelector('input[type="checkbox"]');
            
            if (checkbox) {{
                // Se é o navio selecionado, mostrar
                if (nomeLayer === navioSelecionado) {{
                    if (!checkbox.checked) {{
                        checkbox.click();
                    }}
                }} else if (naviosDisponiveis.includes(nomeLayer)) {{
                    // Se é outro navio, ocultar
                    if (checkbox.checked) {{
                        checkbox.click();
                    }}
                }}
            }}
        }}
    }});
}}

function aplicarFiltros() {{
    var navioSelecionado = document.getElementById('filtro-navio').value;
    var dataInicio = new Date(document.getElementById('filtro-data-inicio').value);
    var dataFim = new Date(document.getElementById('filtro-data-fim').value);
    dataFim.setHours(23, 59, 59, 999); // Incluir o dia inteiro
    
    // Validar datas
    if (dataInicio > dataFim) {{
        alert('⚠️ A data inicial deve ser anterior à data final!');
        return;
    }}
    
    // Controlar visualização dos layers
    controlarLayersNavios(navioSelecionado);
    
    // Atualizar informações
    var infoDiv = document.getElementById('info-filtros');
    var dataInicioStr = document.getElementById('filtro-data-inicio').value;
    var dataFimStr = document.getElementById('filtro-data-fim').value;
    
    // Contar pontos do navio selecionado no período
    var dadosNavio = dadosNavios[navioSelecionado] || [];
    var pontosFiltrados = dadosNavio.filter(function(ponto) {{
        var dataPonto = new Date(ponto.datahora);
        return dataPonto >= dataInicio && dataPonto <= dataFim;
    }});
    
    infoDiv.innerHTML = `
        <b>🚢 ${{navioSelecionado}}</b><br/>
        📅 ${{dataInicioStr}} a ${{dataFimStr}}<br/>
        📍 ${{pontosFiltrados.length}} pontos no período
    `;
    
    console.log('Filtros aplicados:', {{
        navio: navioSelecionado,
        dataInicio: dataInicioStr,
        dataFim: dataFimStr,
        pontosVisiveis: pontosFiltrados.length
    }});
}}

// Aplicar filtros iniciais ao carregar a página
window.addEventListener('load', function() {{
    setTimeout(function() {{
        aplicarFiltros();
    }}, 500);
}});

// Aplicar filtros ao pressionar Enter nos campos de data
document.getElementById('filtro-data-inicio').addEventListener('keypress', function(e) {{
    if (e.key === 'Enter') aplicarFiltros();
}});

document.getElementById('filtro-data-fim').addEventListener('keypress', function(e) {{
    if (e.key === 'Enter') aplicarFiltros();
}});

// Aplicar filtros ao mudar o navio
document.getElementById('filtro-navio').addEventListener('change', function() {{
    aplicarFiltros();
}});
</script>
'''

mapa.get_root().html.add_child(folium.Element(filtros_html))

# ===========================
# 11. SALVAR MAPA HTML
# ===========================
output_file = '/home/ubuntu/mapa_navios_interativo.html'
print(f"\nSalvando mapa em: {output_file}")
mapa.save(output_file)

print("\n" + "="*60)
print("✅ MAPA INTERATIVO CRIADO COM SUCESSO!")
print("="*60)
print(f"Arquivo: {output_file}")
print(f"Navios processados: {len(navios)}")
print(f"Total de pontos plotados: {len(df)}")
print(f"Período: {df['DATAHORA'].min()} até {df['DATAHORA'].max()}")
print("\nRecursos incluídos:")
print("  ✓ Filtros interativos (navio e período)")
print("  ✓ Espectro de cores por velocidade")
print("  ✓ Setas indicando rumo")
print("  ✓ Linha de trajetória conectada")
print("  ✓ Ícone de âncora no primeiro EM PORTO")
print("  ✓ Popups com informações detalhadas")
print("  ✓ Legenda com session IDs")
print("  ✓ Controles de camadas e medição")
print("  ✓ Modo tela cheia")
print("="*60)
