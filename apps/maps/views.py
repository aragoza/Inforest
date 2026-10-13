from django.shortcuts import render

LAYERS = [
    ('cover', 'Forêts actuelles'),
    ('loss', 'Déforestation'),
    ('gain', 'Regain de couverture'),
]


def forest_map(request):
    current_layer = request.GET.get('layer', 'cover')
    if current_layer not in dict(LAYERS):
        current_layer = 'cover'

    return render(request, 'maps/map.html', {
        'layers': LAYERS,
        'current_layer': current_layer,
    })