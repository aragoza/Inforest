from django.shortcuts import render

THEMES = [
    ('science', 'Informations scientifiques'),
    ('loss', 'Pertes de couverture'),
    ('div', 'Informations diverses'),
]

DISCOVERY = [
    {'id': 1, 'theme': 'science',
     'title': 'Les mycorhizes relient les arbres entre eux',
     'summary': "Sous terre, un réseau de champignons échange nutriments et signaux."},
    {'id': 2, 'theme': 'science',
     'title': 'Comment mesure-t-on la canopée depuis l\'espace',
     'summary': "Les satellites Landsat observent la végétation depuis 1972."},
    {'id': 3, 'theme': 'loss',
     'title': "L'Amazonie a perdu 2,3 % de sa canopée en 2025",
     'summary': "Une surface équivalente à deux fois la Belgique."},
    {'id': 4, 'theme': 'loss',
     'title': 'Les incendies, première cause de perte en zone boréale',
     'summary': "Le Canada et la Russie concentrent l'essentiel des surfaces brûlées."},
    {'id': 5, 'theme': 'div',
     'title': 'Un chêne peut vivre plus de 500 ans',
     'summary': "Certains sujets européens dépassent le millénaire."},
    {'id': 6, 'theme': 'div',
     'title': 'La forêt de Białowieża est la dernière forêt primaire d\'Europe',
     'summary': "Elle s'étend sur la frontière entre la Pologne et la Biélorussie."},
]


def discovery_list(request):
    query = request.GET.get('q', '').strip()

    items = DISCOVERY
    if query:
        items = [i for i in DISCOVERY if query.lower() in i['title'].lower()]

    groups = [
        {'key': key, 'label': label,
         'items': [i for i in items if i['theme'] == key]}
        for key, label in THEMES
    ]

    return render(request, 'discovery/list.html', {
        'groups': groups,
        'query': query,
        'total': len(items),
    })


def discovery_detail(request, pk):
    item = next((i for i in DISCOVERY if i['id'] == pk), None)
    label = dict(THEMES).get(item['theme']) if item else ''
    return render(request, 'discovery/detail.html', {'item': item, 'label': label})