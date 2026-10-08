from django.shortcuts import render
from django.shortcuts import redirect

NEWS = [
    {'id': 1, 'titre': 'Feux de forêt maîtrisés dans les Landes',
     'source': 'Mongabay', 'pays': 'France', 'date': 'il y a 4 h'},
    {'id': 2, 'titre': "L'Indonésie annonce un vaste plan de reforestation",
     'source': 'Mongabay', 'pays': 'Monde', 'date': 'il y a 1 j'},
]


def liste(request):
    return render(request, 'news/list.html', {'news': NEWS})

def detail(request, pk):
    news = next((a for a in NEWS if a['id'] == pk), None)
    return render(request, 'news/detail.html', {'news': news})

def lire(request, pk):
    return redirect('news:detail', pk=pk)