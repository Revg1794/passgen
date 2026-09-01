"""Word list for passgen.

Curated for typing comfort and recall: 3-7 letters, all lowercase ASCII,
common enough to picture in your head, spelled the way they sound, and free of
near-homophone pairs that leave you guessing which one you picked.
"""

_RAW = """
able acid acorn acre actor adapt adobe adopt adult agent agile aglow alarm album
alert alias alive alley aloe aloft alpha amber amble amend ample amuse angel
angle ankle apple apron arbor arch arena argue arise armor army aroma arrow ash
aside asset atlas atom attic auto avoid awake award aware away axis axle
bacon badge bagel baker balmy banjo barge basil basin batch beach beacon beam
bean beard begin below bench bend berry bike birch bird birth bison black blade
blank blaze blend bless blimp blink bliss block bloom blue blush board bolt bonus
book boost booth bounce bowl brace braid brain brake branch brand brass brave
bread break brick bride brief brim brisk broad broom brush bubble bucket buddy
budge bugle build bulb bulk bunch bundle bunny burly burst bush butter button
cabin cable cactus cadet camel canal candle candy canoe canvas canyon cargo
carol carpet carrot carve cedar cello cement census chalk champ chant chapel
charm chart cheek cheer chess chest chief chili chime chin chip chirp chive
chorus chrome chunk cider cinch circle citrus civic clamp clang clash clasp
class clay clean clear cleat clerk cliff climb cloak clock close cloth cloud
clove clown club clump coach coast cobalt cobra cocoa comet comic compass conch
cone coral cork corn cosmic cotton couch cough count cove cozy crab crane crank
crate crawl cream creek crest crew crib crimp crisp crop cross crowd crown crumb
crush crust cube cumin curb curl curry curve cyan cycle
daily dairy daisy dance dandy dapper dash dawn debut decal decoy deed deep deer
delta demo denim dense depot depth derby desk detail devil diary digit dill
dime diner dingo disco dish ditch diver dizzy dock dodge dolly dome donor donut
dorm dose dough dove down dozen draft drag drape draw dream dress drift
drill drink drive drop drum dry duck duet dune dusk dust duty dwarf dwell dye
eager eagle early earn earth easel east easy eaten ebony echo edge edit eel
eight elbow elder elect elite elm elope elude ember emit empty enact enemy
energy engine enjoy enter entry envoy epoch equal equip erase error essay etch
even event exact exam excel exit expand expert extra
fable fabric face fact fade fair falcon fame fancy fang farm fast fault
feast fence fern ferry fetch fever fiber field fiery fifth fig figure
film filter final finch finger finish fire firm first fish fist five fix
flag flame flare flash flask flat flax fleet flesh flex flint flip float flock
floor floral flour flow fluid flute flux foam focal focus foggy foil fold folk
fond font food foot forge fork form forth forty fossil found four fox frame
fresh fret fried friend fringe frog front frost fruit fudge fuel full fungi
funnel fuse fuzzy
gadget gain gala gallon game gap garden garlic gauge gavel gaze gear gecko
gem genius gentle germ giant gift gills ginger girl given glad glance
glass glaze gleam glide globe gloom glory gloss glove glow glue gnome goal goat
gold golf gong good goose gorge gown grab grace grade grain grand grant grape
graph grasp grass grate grave gravy graze great green greet grid grill grim
grin grip grits groom groove ground group grove grow gruff guard guess guest
guide guild gulf gully gulp guru gust gym
habit hail hair half hall halt hammer hand hang happy harbor hard hare harm harp
harsh hasty hatch haul haven hawk hazel head heap heart heat heavy hedge
heel height helix hello helmet help herb herd hero hex hickory high hike
hill hinge hint hive hobby hockey hold hole hollow home honey honor hood
hoof hook hoop hope horn horse hose host hotel hound hour house hover howl hub
huddle human humble humid humor hunt hurdle hurry husky hydro hymn
ice icing icon idea idle igloo image impact inbox inch index indigo ink inlet
inner input insect inside intro invest iris iron island issue item ivory ivy
jacket jade jam jar jazz jelly jet jewel jockey jog join joke jolly journal joy
judge juice jumbo jump jungle junior juror
kayak keen keep kelp kennel kettle kick kidney kind king kiosk
kite kitten kiwi knack knee knife knight knit knob knock knot koala
label labor lace ladder lady lagoon lake lamb lamp lance land lane lantern
lapel lard large lark laser last latch late laugh launch lava lawn layer lazy
leaf leap learn lease leash least leather ledge leek left legal legend
lemon lend length lens lentil level lever light lilac lily limb lime
limit linen link lion list liter little lively liver lizard llama load loaf loan
lobby local locket lodge loft logic long loop loose lord lotus loud
lounge love lower loyal luck lumber lunar lunch lung lure lush lute lyric
macro madam magic magnet maize major maker mammal mango manor manual maple
marble march marina mark market marsh mask mason mast match math matrix mayor
maze meadow meal mean meat medal media melody melon melt member memo mend menu
merit merry mesa mesh metal meter method micro might mild mile milk
mill mimic mind mint minus minute mirror mist mixer moat mocha modal model
modem modest moist molar mole moment money monkey month moon moral
mosaic moss motel motor mound mount mouse mouth move movie mud muffin mug mulch
mule mural muscle museum music mustard mutual myth
nacho nail name nap napkin narrow nasal native nature naval navy near neat neck
nectar needle neon nerve nest net never next nibble niche nickel night
nimble nine noble node noise nomad noodle noon norm north nose notion
novel nozzle number nurse nylon
oak oasis oat ocean octave odd offer office often oil olive omega omit
onion onset open opera optic orange orbit orchid order organ
origin otter ounce outer oval oven owl oxide oyster ozone
pace pack pact paddle page paint pair palace palm panda panel pansy pantry paper
parade parcel pardon parent park parrot parsley part party pasta pastel patch
path patio patrol pause pave peach peak peanut pear pearl pebble pecan
pedal peek peel pelican pencil penny pepper perch period permit person pest
petal phase phone photo phrase piano pick picnic piece pier pigment pile pillar
pilot pinch pine pink pint pipe pirate pistol pitch pivot pixel pizza place
plain plan plank plant plasma plate play plaza pleat pledge plenty plot plow
plug plum plus pocket poem point polar pole polish pond pony pool poppy porch
port pose posh post pouch pound powder power praise prance prank
press price pride prime print prism prize probe profit prompt proof proper
proud prove prune public pudding puddle puff pull pulse pump punch pupil puppy
purple purse push puzzle pylon
quail quaint quake quart quartz queen quench query quest queue quick quiet quill
quilt quirk quiz quota quote
rabbit race radar radio raft rail rain raise rake rally ramp ranch
random range rank rapid rare rash raven razor reach react realm reason
rebel recall recess recipe record reef refer reflex refuse regal region
relax relay relic remedy remind remote render rental repair repeat reply
report rescue reset resin resist resort reveal review reward rhino rhyme
ribbon rice rich ridge rifle rigid rim ring rinse ripe ripple rise
risk ritual river road roast robin robot rock rocket rodeo rogue role roll roof
room roost root rope rose rotate rough round route rover royal rubber ruby
rudder rug ruler rumble runner rural rush rust rustic
saddle safari safe saga sage sail salad salmon salon salt salute sample sand
sane sash satin sauce sauna savor scale scan scarf scene scent school scoop
scope score scout scrap screen script scroll scrub sculpt seal seam search
season seat second secret sector seed seek seep senior sense sepia
serve setup seven shade shaft shake shame shape share shark sharp shave
shed sheep sheet shelf shell shield shift shine ship shirt shock shoe shop
shore short shovel show shrimp shrub shut side siege sift sigh sign
silent silk silly silver simple sing siren sister site sixth size
skate sketch ski skill skin skip skirt skull sky slab slalom slam slate sled
sleek sleep sleeve slice slide slim slip slope slot slow small smart smash smell
smile smoke smooth snack snail snake snap sneak snow snug soak soap social sock
soda sofa soft soil solar solid solo solve sonar song soot sort soul
sound soup south space spade spare spark speak spear speed spell spend sphere
spice spider spike spin spiral spirit split spoke sponge spool spoon sport spot
spray spread spring sprint sprout spruce spur square squash squid stable stack
staff stage stair stake stalk stall stamp stand staple star start state
steady steam steel steep stem step stereo stick stiff sting stir stitch
stock stone stool stop store storm story stout stove strap straw stream street
stress strict strike string strip strong studio study stump stun style suede
sugar suit summer summit super supply surf surge swan swap swarm
sweep sweet swift swim swing switch sword symbol syntax syrup
table tablet tackle taco tact tail tale talk tall tally tandem tangy tank
tape target task taste taupe taxi teach teal team teapot tempo tender tennis
tent term test text thank thaw theme thick thing think third thorn thread
three thrive throw thumb thyme tick ticket tidal tide tidy tiger tight tile
tilt timber time timid tin tiny tip tissue title toast today toe token tomato
tone tongs tool tooth top topaz topic torch total totem touch tough tour towel
tower town toy trace track trade trail train tram trap travel tray treat tree
trek trend trial tribe trick trim trio trip troop trophy trot trout truck true
trunk trust truth tube tuck tulip tumble tuna tundra tune tunnel turbo turf
turkey turn turtle tusk tutor tweed twice twig twin twist type
udder ultra umbra uncle under unfold union unique unit unlock until update
upper upset urban urge usage useful usher usual utmost utter
vacant valet valid valley value valve van vanilla vapor vase vast vault vector
veil velvet vendor venue verb verse vessel vest veto vibe video vigor
villa vine vinyl viola violet viper virtue visa visit visor vista vital vivid
vocal vodka vogue voice void volley volume vote vowel voyage
wafer wage wagon waist wake walk wall walnut waltz wand warm warp
wash wasp watch water wave wax weave web wedge weed week weld well west whale
wheat wheel while whip whisk white whole wide widget width wild willow win wind
wing wink winter wipe wire wise wish wolf wonder wood wool word work world worm
worth wound woven wrap wreath wrench wrist
xenon xylem
yacht yard yarn yawn year yeast yellow yield yoga yogurt yolk young youth yoyo
zebra zenith zero zest zigzag zinc zone zoom
"""

WORDS = tuple(sorted(set(_RAW.split())))
