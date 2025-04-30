import faker

fake = faker.Faker()

class FakeReplacer:
    @staticmethod
    def replace_entities(text: str, entities: list):
        
        replacements = []
        
        i = 0
        while i < len(entities):
            entity_text = entities[i]['word'].replace('▁', '')
            entity_type = entities[i]['entity'][2:]
            start_pos = entities[i]['start']
            end_pos = entities[i]['end']
            j = i + 1
            
            while j < len(entities) and entities[j]['entity'].startswith('I-') and entities[j]['entity'][2:] == entity_type:
                if entities[j]['start'] == end_pos:
                    entity_text += entities[j]['word'].replace('▁', '')
                    end_pos = entities[j]['end']
                else:
                    break
                j += 1
                
            replacements.append((start_pos, end_pos, entity_text, entity_type))
            i = j
        
        for start_pos, end_pos, entity_text, entity_type in sorted(replacements, reverse=True):
            if entity_type == 'PER':
                fake_name = fake.name()
                text = text[:start_pos] + fake_name + text[end_pos:]
            elif entity_type == 'ORG':
                fake_org = fake.company()
                text = text[:start_pos] + fake_org + text[end_pos:]
            elif entity_type == 'LOC':
                fake_loc = fake.city()
                text = text[:start_pos] + fake_loc + text[end_pos:]
        
        return text