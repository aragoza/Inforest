from django.shortcuts import render

THEMES = [
    ('science', 'Informations scientifiques'),
    ('loss', 'Pertes de couverture'),
    ('div', 'Informations diverses'),
]

DISCOVERIES = [
    {
        'id': 1,
        'theme': 'science',
        'title': 'Les mycorhizes relient les arbres entre eux',
        'summary': "Sous terre, un réseau de champignons échange nutriments et signaux.",
    },
    {
        'id': 2,
        'theme': 'science',
        'title': "Comment mesure-t-on la canopée depuis l'espace",
        'summary': "Les satellites Landsat observent la végétation depuis 1972.",
    },
    {
        'id': 3,
        'theme': 'loss',
        'title': "L'Amazonie a perdu 2,3 % de sa canopée en 2025",
        'summary': "Une surface équivalente à deux fois la Belgique.",
    },
    {
        'id': 4,
        'theme': 'loss',
        'title': 'Les incendies, première cause de perte en zone boréale',
        'summary': "Le Canada et la Russie concentrent l'essentiel des surfaces brûlées.",
    },
    {
        'id': 5,
        'theme': 'div',
        'title': 'Un chêne peut vivre plus de 500 ans',
        'summary': "Certains sujets européens dépassent le millénaire.",
    },
    {
        'id': 6,
        'theme': 'div',
        'title': "La forêt de Białowieża est la dernière forêt primaire d'Europe",
        'summary': "Elle s'étend sur la frontière entre la Pologne et la Biélorussie.",
    },
]


def discovery_list(request):
    query = request.GET.get('q', '').strip()

    discoveries = DISCOVERIES
    if query:
        discoveries = [
            d for d in DISCOVERIES if query.lower() in d['title'].lower()
        ]

    groups = [
        {
            'key': key,
            'label': label,
            'entries': [d for d in discoveries if d['theme'] == key],
        }
        for key, label in THEMES
    ]

    return render(request, 'discovery/list.html', {
        'groups': groups,
        'query': query,
        'total': len(discoveries),
    })


def discovery_detail(request, pk):
    discovery = next((d for d in DISCOVERIES if d['id'] == pk), None)
    theme_label = dict(THEMES).get(discovery['theme']) if discovery else ''
    return render(request, 'discovery/detail.html', {
        'discovery': discovery,
        'theme_label': theme_label,
    })