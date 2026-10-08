from django.shortcuts import render

LAYERS = [
    ('cover', 'Forêts actuelles'),
    ('loss', 'Déforestation'),
    ('gain', 'Regain de couverture'),
]


def forest_map(request):
    current = request.GET.get('layer', 'cover')
    return render(request, 'maps/map.html', {
        'layers': LAYERS,
        'current': current,
    })